import base64
import asyncio
import unittest
import requests
from unittest.mock import MagicMock
from unittest.mock import patch

from agent import TripletexAgent
from main import health
from schemas import SolveFile, SolveRequest
from tripletex_client import TripletexClient


class AppTests(unittest.TestCase):
    def test_health_function(self) -> None:
        self.assertEqual(health(), {"status": "ok"})

    def test_solve_file_accepts_mime_type(self) -> None:
        solve_file = SolveFile(
            filename="receipt.pdf",
            content_base64="ZGF0YQ==",
            mime_type="application/pdf",
        )

        self.assertEqual(
            solve_file.model_dump(),
            {
                "filename": "receipt.pdf",
                "content_base64": "ZGF0YQ==",
                "mime_type": "application/pdf",
            },
        )

    def test_save_files_preserves_mime_type_metadata(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        request_payload = {
            "prompt": "Create customer Acme AS",
            "files": [
                {
                    "filename": "receipt.pdf",
                    "content_base64": base64.b64encode(b"demo").decode("ascii"),
                    "mime_type": "application/pdf",
                }
            ],
            "tripletex_credentials": {
                "base_url": "https://example.test/v2",
                "session_token": "dummy-token",
            },
        }

        from schemas import SolveRequest

        request = SolveRequest.model_validate(request_payload)
        saved_files = agent._save_files(request)

        self.assertEqual(len(saved_files), 1)
        self.assertEqual(saved_files[0].filename, "receipt.pdf")
        self.assertEqual(saved_files[0].mime_type, "application/pdf")
        self.assertTrue(saved_files[0].path.endswith("attachments/receipt.pdf"))

    def test_apply_attachment_context_derives_travel_expense_title_from_receipt(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Create travel expense from attached receipt")
        saved_files = [
            agent._save_files(
                SolveRequest.model_validate(
                    {
                        "prompt": "Create travel expense from attached receipt",
                        "files": [
                            {
                                "filename": "Oslo-trip-march.pdf",
                                "content_base64": base64.b64encode(b"demo").decode("ascii"),
                                "mime_type": "application/pdf",
                            }
                        ],
                        "tripletex_credentials": {
                            "base_url": "https://example.test/v2",
                            "session_token": "dummy-token",
                        },
                    }
                )
            )[0]
        ]

        agent._apply_attachment_context(plan, saved_files)

        self.assertEqual(plan.extracted["title"], "Oslo trip march")
        self.assertEqual(
            plan.steps[0].params["attachment_context"]["source_filename"],
            "Oslo-trip-march.pdf",
        )

    def test_apply_attachment_context_derives_customer_fields_from_attachment_text(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Create customer from attached file")
        saved_files = [
            agent._save_files(
                SolveRequest.model_validate(
                    {
                        "prompt": "Create customer from attached file",
                        "files": [
                            {
                                "filename": "customer.txt",
                                "content_base64": base64.b64encode(
                                    b"Customer: Acme AS\nEmail: post@acme.no\n"
                                ).decode("ascii"),
                                "mime_type": "text/plain",
                            }
                        ],
                        "tripletex_credentials": {
                            "base_url": "https://example.test/v2",
                            "session_token": "dummy-token",
                        },
                    }
                )
            )[0]
        ]

        agent._apply_attachment_context(plan, saved_files)

        self.assertEqual(plan.extracted["name"], "Acme AS")
        self.assertEqual(plan.extracted["email"], "post@acme.no")
        self.assertEqual(
            plan.steps[0].params["attachment_context"]["source_filename"],
            "customer.txt",
        )

    def test_solve_includes_normalized_prompt_for_supported_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_customers.return_value = [
            {"id": 10, "name": "Acme AS", "email": None}
        ]

        from schemas import SolveRequest

        request = SolveRequest.model_validate(
            {
                "prompt": "Crear cliente Acme AS",
                "files": [],
                "tripletex_credentials": {
                    "base_url": "https://example.test/v2",
                    "session_token": "dummy-token",
                },
            }
        )

        result = asyncio.run(agent.solve(request))

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["debug"]["normalized_prompt"], "create customer Acme AS")
        self.assertEqual(result["debug"]["task_type"], "customer_create")
        self.assertEqual(result["debug"]["plan_steps"][0]["action"], "customer_create")
        self.assertEqual(result["debug"]["plan_steps"][0]["name"], "create_customer")

    def test_solve_uses_attachment_text_for_customer_create(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_customers.side_effect = [
            [],
            [{"id": 77, "name": "Acme AS", "email": "post@acme.no"}],
        ]
        agent.client.create_customer.return_value = {
            "id": 77,
            "name": "Acme AS",
            "email": "post@acme.no",
        }

        request = SolveRequest.model_validate(
            {
                "prompt": "Create customer from attached file",
                "files": [
                    {
                        "filename": "customer.txt",
                        "content_base64": base64.b64encode(
                            b"Customer: Acme AS\nEmail: post@acme.no\n"
                        ).decode("ascii"),
                        "mime_type": "text/plain",
                    }
                ],
                "tripletex_credentials": {
                    "base_url": "https://example.test/v2",
                    "session_token": "dummy-token",
                },
            }
        )

        result = asyncio.run(agent.solve(request))

        agent.client.create_customer.assert_called_once_with(
            name="Acme AS",
            email="post@acme.no",
        )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["debug"]["task_type"], "customer_create")
        self.assertEqual(
            result["debug"]["attachment_context"]["source_filename"],
            "customer.txt",
        )

    def test_solve_includes_unsupported_debug_for_payment_prompt(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        from schemas import SolveRequest

        request = SolveRequest.model_validate(
            {
                "prompt": "Registrar pago para factura Acme AS",
                "files": [],
                "tripletex_credentials": {
                    "base_url": "https://example.test/v2",
                    "session_token": "dummy-token",
                },
            }
        )

        result = asyncio.run(agent.solve(request))

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["debug"]["normalized_prompt"], "register payment para invoice Acme AS")
        self.assertTrue(result["debug"]["unsupported"])
        self.assertFalse(result["debug"]["implemented"])
        self.assertEqual(result["debug"]["unsupported_task_type"], "payment_unsupported")
        self.assertEqual(result["debug"]["plan_steps"][0]["action"], "payment_unsupported")

    def test_solve_failure_preserves_task_type_and_plan_steps(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_customers.return_value = []

        from schemas import SolveRequest

        request = SolveRequest.model_validate(
            {
                "prompt": "Update customer Acme AS with email post@acme.no",
                "files": [],
                "tripletex_credentials": {
                    "base_url": "https://example.test/v2",
                    "session_token": "dummy-token",
                },
            }
        )

        result = asyncio.run(agent.solve(request))

        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["debug"]["task_type"], "customer_update")
        self.assertEqual(result["debug"]["plan_steps"][0]["action"], "customer_update")
        self.assertIn('Customer "Acme AS" was not found', result["debug"]["error"])

    def test_extract_employee_fields_detects_account_administrator(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_employee_fields(
            "Opprett ansatt Ola Nordmann med e-post ola@example.org. Han skal være kontoadministrator."
        )

        self.assertEqual(parsed["first_name"], "Ola")
        self.assertEqual(parsed["last_name"], "Nordmann")
        self.assertEqual(parsed["email"], "ola@example.org")
        self.assertTrue(parsed["is_account_administrator"])

    def test_extract_employee_fields_supports_accented_names(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_employee_fields(
            "Create employee José Álvarez with email jose@example.org"
        )

        self.assertEqual(parsed["first_name"], "José")
        self.assertEqual(parsed["last_name"], "Álvarez")
        self.assertEqual(parsed["email"], "jose@example.org")

    def test_handle_create_employee_grants_entitlements_for_account_admin(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_employees.side_effect = [
            [],
            [
                {
                    "id": 123,
                    "firstName": "Ola",
                    "lastName": "Nordmann",
                    "email": "ola@example.org",
                    "userType": "EXTENDED",
                }
            ],
        ]
        agent.client.get_default_department.return_value = {
            "id": 55,
            "name": "Default Department",
            "isInactive": False,
        }
        agent.client.create_employee.return_value = {
            "id": 123,
            "firstName": "Ola",
            "lastName": "Nordmann",
            "email": "ola@example.org",
            "userType": "EXTENDED",
        }
        agent.client.list_employee_entitlements.side_effect = [
            [{"id": 1, "name": "AUTH_EMPLOYEE_INFO"}],
            [{"id": 1, "name": "ROLE_ADMINISTRATOR"}],
        ]

        result = agent._handle_create_employee(
            {
                "first_name": "Ola",
                "last_name": "Nordmann",
                "email": "ola@example.org",
                "is_account_administrator": True,
            }
        )

        agent.client.create_employee.assert_called_once_with(
            first_name="Ola",
            last_name="Nordmann",
            email="ola@example.org",
            user_type="EXTENDED",
            department_id=55,
        )
        agent.client.grant_employee_entitlements_by_template.assert_called_once_with(
            employee_id=123,
            template="ALL_PRIVILEGES",
        )
        self.assertEqual(result["message"], "Employee created successfully")
        self.assertTrue(result["debug"]["verified"])
        self.assertEqual(result["debug"]["entitlement_count"], 1)
        self.assertEqual(result["debug"]["created_employee_user_type"], "EXTENDED")
        self.assertEqual(result["debug"]["department_id"], 55)
        self.assertTrue(result["debug"]["has_account_administrator_entitlement"])
        self.assertFalse(
            agent._has_account_administrator_entitlement(
                [{"id": 1, "name": "AUTH_EMPLOYEE_INFO"}]
            )
        )

    def test_handle_response_allows_empty_success_body(self) -> None:
        client = TripletexClient(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        response = MagicMock()
        response.ok = True
        response.json.side_effect = ValueError("no json")

        self.assertEqual(client._handle_response(response), {})

    def test_extract_invoice_fields(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_invoice_fields(
            "Opprett faktura for kunde Acme AS med produkt Konsulenttime antall 2"
        )

        self.assertEqual(parsed["customer_name"], "Acme AS")
        self.assertEqual(parsed["product_name"], "Konsulenttime")
        self.assertEqual(parsed["quantity"], 2.0)

    def test_build_plan_normalizes_spanish_customer_create(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Crear cliente Acme AS")

        self.assertEqual(plan.task_type, "customer_create")
        self.assertEqual(plan.extracted["name"], "Acme AS")

    def test_build_plan_normalizes_spanish_product_create(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Crear producto Consejo con descripción Texto nuevo")

        self.assertEqual(plan.task_type, "product_create")
        self.assertEqual(plan.extracted["name"], "Consejo")
        self.assertEqual(plan.extracted["description"], "Texto nuevo")

    def test_build_plan_normalizes_portuguese_customer_update(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Atualizar cliente Acme AS com email post@acme.no")

        self.assertEqual(plan.task_type, "customer_update")
        self.assertEqual(plan.extracted["name"], "Acme AS")
        self.assertEqual(plan.extracted["email"], "post@acme.no")

    def test_build_plan_normalizes_german_project_delete(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Lösche Projekt Alpha")

        self.assertEqual(plan.task_type, "project_delete")
        self.assertEqual(plan.extracted["name"], "Alpha")

    def test_build_plan_normalizes_french_invoice_create(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan(
            "Créer facture pour client Acme AS avec produit Conseil quantité 2"
        )

        self.assertEqual(plan.task_type, "invoice_create")
        self.assertEqual(plan.extracted["customer_name"], "Acme AS")
        self.assertEqual(plan.extracted["product_name"], "Conseil")
        self.assertEqual(plan.extracted["quantity"], 2.0)

    def test_build_plan_normalizes_nynorsk_create_keyword(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Lag kunde Acme AS")

        self.assertEqual(plan.task_type, "customer_create")
        self.assertEqual(plan.extracted["name"], "Acme AS")

    def test_build_plan_normalizes_spanish_employee_admin_create(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan(
            "Crear empleado Ola Nordmann con email ola@example.org administrador de cuenta"
        )

        self.assertEqual(plan.task_type, "employee_create")
        self.assertEqual(plan.extracted["first_name"], "Ola")
        self.assertEqual(plan.extracted["last_name"], "Nordmann")
        self.assertTrue(plan.extracted["is_account_administrator"])

    def test_build_plan_normalizes_french_employee_admin_create_with_accents(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan(
            "Créer employé José Álvarez avec email jose@example.org administrateur du compte"
        )

        self.assertEqual(plan.task_type, "employee_create")
        self.assertEqual(plan.extracted["first_name"], "José")
        self.assertEqual(plan.extracted["last_name"], "Álvarez")
        self.assertTrue(plan.extracted["is_account_administrator"])

    def test_build_plan_normalizes_french_travel_expense_update(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan(
            "Mettre à jour note de frais Oslo mars to Bergen mars"
        )

        self.assertEqual(plan.task_type, "travel_expense_update")
        self.assertEqual(plan.extracted["title"], "Oslo mars")
        self.assertEqual(plan.extracted["updated_title"], "Bergen mars")

    def test_build_plan_normalizes_portuguese_order_delete(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan(
            "Excluir pedido for customer Acme AS with product Konsulenttime"
        )

        self.assertEqual(plan.task_type, "order_delete")
        self.assertEqual(plan.extracted["customer_name"], "Acme AS")
        self.assertEqual(plan.extracted["product_name"], "Konsulenttime")

    def test_build_plan_normalizes_german_travel_expense_create(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Erstelle Reisekostenabrechnung Berlin April")

        self.assertEqual(plan.task_type, "travel_expense_create")
        self.assertEqual(plan.extracted["title"], "Berlin April")

    def test_build_plan_normalizes_german_employee_create_with_email(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan(
            "Erstelle employee André Müller mit email andre@example.org"
        )

        self.assertEqual(plan.task_type, "employee_create")
        self.assertEqual(plan.extracted["first_name"], "André")
        self.assertEqual(plan.extracted["last_name"], "Müller")
        self.assertEqual(plan.extracted["email"], "andre@example.org")

    def test_build_plan_normalizes_french_product_update(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan(
            "Mettre à jour produit Conseil avec description Nouvelle tekst"
        )

        self.assertEqual(plan.task_type, "product_update")
        self.assertEqual(plan.extracted["name"], "Conseil")
        self.assertEqual(plan.extracted["description"], "Nouvelle tekst")

    def test_build_plan_normalizes_portuguese_project_update(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Atualizar projeto Alpha para cliente Beta AS")

        self.assertEqual(plan.task_type, "project_update")
        self.assertEqual(plan.extracted["name"], "Alpha")
        self.assertEqual(plan.extracted["customer_name"], "Beta AS")

    def test_build_plan_normalizes_german_department_update_number(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan(
            "Aktualisiere Abteilung Vertrieb Abteilungsnummer 202"
        )

        self.assertEqual(plan.task_type, "department_update")
        self.assertEqual(plan.extracted["name"], "Vertrieb")
        self.assertEqual(plan.extracted["department_number"], "202")

    def test_build_plan_normalizes_german_department_create_with_number(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Erstelle department Vertrieb mit nummer 202")

        self.assertEqual(plan.task_type, "department_create")
        self.assertEqual(plan.extracted["name"], "Vertrieb")
        self.assertEqual(plan.extracted["department_number"], "202")

    def test_build_plan_normalizes_spanish_department_delete_without_swallowing_number(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Eliminar departamento Ventas número de departamento 202")

        self.assertEqual(plan.task_type, "department_delete")
        self.assertEqual(plan.extracted["name"], "Ventas")

    def test_build_plan_normalizes_spanish_department_create_without_swallowing_number(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Crear departamento Ventas con número de departamento 202")

        self.assertEqual(plan.task_type, "department_create")
        self.assertEqual(plan.extracted["name"], "Ventas")
        self.assertEqual(plan.extracted["department_number"], "202")

    def test_build_plan_normalizes_french_department_create_without_swallowing_description(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Créer department Sales avec description Nouvelle")

        self.assertEqual(plan.task_type, "department_create")
        self.assertEqual(plan.extracted["name"], "Sales")

    def test_build_plan_classifies_invoice_delete_as_unsupported_invoice_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan(
            "Supprimer invoice pour client Acme AS avec produit Conseil quantité 2"
        )

        self.assertEqual(plan.task_type, "invoice_delete")
        self.assertEqual(plan.steps[0].action, "invoice_delete")

    def test_build_plan_classifies_invoice_update_as_unsupported_invoice_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Update invoice for customer Acme AS")

        self.assertEqual(plan.task_type, "invoice_update")
        self.assertEqual(plan.steps[0].action, "invoice_update")

    def test_build_plan_classifies_order_update_as_unsupported_order_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Update order for customer Acme AS")

        self.assertEqual(plan.task_type, "order_update")
        self.assertEqual(plan.steps[0].action, "order_update")

    def test_build_plan_classifies_employee_update_as_unsupported_employee_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Update employee José Álvarez with email jose@example.org")

        self.assertEqual(plan.task_type, "employee_update")
        self.assertEqual(plan.steps[0].action, "employee_update")

    def test_build_plan_classifies_employee_delete_as_unsupported_employee_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Delete employee José Álvarez")

        self.assertEqual(plan.task_type, "employee_delete")
        self.assertEqual(plan.steps[0].action, "employee_delete")

    def test_build_plan_classifies_payment_prompt_as_unsupported_payment_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Register payment for invoice Acme AS")

        self.assertEqual(plan.task_type, "payment_unsupported")
        self.assertEqual(plan.steps[0].action, "payment_unsupported")

    def test_build_plan_classifies_credit_note_prompt_as_unsupported_credit_note_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Crear nota de crédito para cliente Acme AS")

        self.assertEqual(plan.task_type, "credit_note_unsupported")
        self.assertEqual(plan.steps[0].action, "credit_note_unsupported")

    def test_build_plan_classifies_voucher_prompt_as_unsupported_voucher_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Create voucher for travel expense")

        self.assertEqual(plan.task_type, "voucher_unsupported")
        self.assertEqual(plan.steps[0].action, "voucher_unsupported")

    def test_build_plan_classifies_french_payment_prompt_as_unsupported_payment_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Supprimer paiement pour facture Acme AS")

        self.assertEqual(plan.task_type, "payment_unsupported")
        self.assertEqual(plan.steps[0].action, "payment_unsupported")

    def test_build_plan_classifies_spanish_payment_prompt_as_unsupported_payment_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Registrar pago para factura Acme AS")

        self.assertEqual(plan.task_type, "payment_unsupported")
        self.assertEqual(plan.steps[0].action, "payment_unsupported")

    def test_build_plan_classifies_german_credit_note_prompt_as_unsupported_credit_note_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Erstelle Gutschrift für kunde Acme AS")

        self.assertEqual(plan.task_type, "credit_note_unsupported")
        self.assertEqual(plan.steps[0].action, "credit_note_unsupported")

    def test_build_plan_classifies_spanish_credit_note_synonyms_as_unsupported_credit_note_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Crear abono para cliente Acme AS")

        self.assertEqual(plan.task_type, "credit_note_unsupported")
        self.assertEqual(plan.steps[0].action, "credit_note_unsupported")

    def test_build_plan_classifies_portuguese_voucher_prompt_as_unsupported_voucher_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Criar voucher Berlin April")

        self.assertEqual(plan.task_type, "voucher_unsupported")
        self.assertEqual(plan.steps[0].action, "voucher_unsupported")

    def test_build_plan_classifies_localized_voucher_synonyms_as_unsupported_voucher_task(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        for prompt in [
            "Criar lançamento Berlin April",
            "Créer écriture Berlin April",
            "Erstelle buchung Berlin April",
        ]:
            plan = agent._build_plan(prompt)
            self.assertEqual(plan.task_type, "voucher_unsupported")
            self.assertEqual(plan.steps[0].action, "voucher_unsupported")

    def test_execute_plan_returns_explicit_payment_unsupported_message(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Register payment for invoice Acme AS")
        result = agent._execute_plan(plan)

        self.assertEqual(result["message"], "Payment workflows are not implemented yet")
        self.assertTrue(result["debug"]["unsupported"])
        self.assertEqual(result["debug"]["unsupported_task_type"], "payment_unsupported")

    def test_execute_plan_returns_explicit_invoice_delete_unsupported_message(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan(
            "Supprimer invoice pour client Acme AS avec produit Conseil quantité 2"
        )
        result = agent._execute_plan(plan)

        self.assertIn("Invoice deletion is not implemented", result["message"])
        self.assertTrue(result["debug"]["unsupported"])
        self.assertEqual(result["debug"]["unsupported_task_type"], "invoice_delete")

    def test_execute_plan_returns_explicit_invoice_update_unsupported_message(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Update invoice for customer Acme AS")
        result = agent._execute_plan(plan)

        self.assertEqual(result["message"], "Invoice update workflows are not implemented yet")
        self.assertTrue(result["debug"]["unsupported"])
        self.assertEqual(result["debug"]["unsupported_task_type"], "invoice_update")

    def test_execute_plan_returns_explicit_order_update_unsupported_message(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Update order for customer Acme AS")
        result = agent._execute_plan(plan)

        self.assertEqual(result["message"], "Order update workflows are not implemented yet")
        self.assertTrue(result["debug"]["unsupported"])
        self.assertEqual(result["debug"]["unsupported_task_type"], "order_update")

    def test_execute_plan_returns_explicit_employee_update_unsupported_message(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Update employee José Álvarez with email jose@example.org")
        result = agent._execute_plan(plan)

        self.assertEqual(result["message"], "Employee update workflows are not implemented yet")
        self.assertTrue(result["debug"]["unsupported"])
        self.assertEqual(result["debug"]["unsupported_task_type"], "employee_update")

    def test_execute_plan_returns_explicit_credit_note_unsupported_message(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Créer avoir pour client Acme AS")
        result = agent._execute_plan(plan)

        self.assertEqual(result["message"], "Credit note workflows are not implemented yet")
        self.assertTrue(result["debug"]["unsupported"])
        self.assertEqual(result["debug"]["unsupported_task_type"], "credit_note_unsupported")

    def test_execute_plan_returns_explicit_voucher_unsupported_message(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        plan = agent._build_plan("Criar voucher Berlin April")
        result = agent._execute_plan(plan)

        self.assertEqual(result["message"], "Voucher workflows are not implemented yet")
        self.assertTrue(result["debug"]["unsupported"])
        self.assertEqual(result["debug"]["unsupported_task_type"], "voucher_unsupported")

    def test_extract_customer_update_fields(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_customer_update_fields(
            "Oppdater kunde Acme AS med e-post post@acme.no"
        )

        self.assertEqual(parsed["name"], "Acme AS")
        self.assertEqual(parsed["email"], "post@acme.no")

    def test_extract_product_delete_fields(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_product_delete_fields("Slett produkt Konsulenttime")

        self.assertEqual(parsed["name"], "Konsulenttime")

    def test_extract_product_update_fields(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_product_update_fields(
            "Oppdater produkt Konsulenttime med beskrivelse Oppdatert tekst"
        )

        self.assertEqual(parsed["name"], "Konsulenttime")
        self.assertEqual(parsed["description"], "Oppdatert tekst")

    def test_extract_department_update_fields(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_department_update_fields(
            "Oppdater avdeling Salg med avdelingsnummer 202"
        )

        self.assertEqual(parsed["name"], "Salg")
        self.assertEqual(parsed["department_number"], "202")

    def test_extract_customer_delete_fields(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_customer_delete_fields("Slett kunde Acme AS")

        self.assertEqual(parsed["name"], "Acme AS")

    def test_extract_department_delete_fields(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_department_delete_fields("Slett avdeling Salg")

        self.assertEqual(parsed["name"], "Salg")

    def test_extract_project_update_fields(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_project_update_fields(
            "Oppdater prosjekt Alpha for kunde Beta AS"
        )

        self.assertEqual(parsed["name"], "Alpha")
        self.assertEqual(parsed["customer_name"], "Beta AS")

    def test_extract_project_delete_fields(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_project_delete_fields("Slett prosjekt Alpha")

        self.assertEqual(parsed["name"], "Alpha")

    def test_extract_travel_expense_fields(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_travel_expense_fields(
            "Opprett reiseregning Oslo tur mars"
        )

        self.assertEqual(parsed["title"], "Oslo tur mars")

    def test_handle_create_travel_expense_supports_attachment_derived_title(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.get_default_employee.return_value = {"id": 7}
        agent.client.create_travel_expense.return_value = {
            "id": 100,
            "title": "Oslo trip march",
            "state": "OPEN",
        }
        agent.client.search_travel_expenses.return_value = [
            {"id": 100, "title": "Oslo trip march", "state": "OPEN"}
        ]

        result = agent._handle_create_travel_expense(
            {
                "title": "Oslo trip march",
                "attachment_context": {
                    "used_for": "travel_expense_title",
                    "source_filename": "Oslo-trip-march.pdf",
                    "derived_title": "Oslo trip march",
                },
            }
        )

        self.assertEqual(result["message"], "Travel expense created successfully")
        self.assertEqual(
            result["debug"]["attachment_context"]["source_filename"],
            "Oslo-trip-march.pdf",
        )
        self.assertTrue(result["debug"]["verified"])

    def test_extract_travel_expense_delete_fields(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_travel_expense_delete_fields(
            "Slett reiseregning Oslo tur mars"
        )

        self.assertEqual(parsed["title"], "Oslo tur mars")

    def test_extract_travel_expense_update_fields(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_travel_expense_update_fields(
            "Oppdater reiseregning Oslo tur mars til Bergen tur mars"
        )

        self.assertEqual(parsed["title"], "Oslo tur mars")
        self.assertEqual(parsed["updated_title"], "Bergen tur mars")

    def test_extract_order_delete_fields(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )

        parsed = agent._extract_order_delete_fields(
            "Slett ordre for kunde Acme AS med produkt Konsulenttime"
        )

        self.assertEqual(parsed["customer_name"], "Acme AS")
        self.assertEqual(parsed["product_name"], "Konsulenttime")

    def test_handle_create_invoice(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_customers.return_value = [{"id": 10, "name": "Acme AS"}]
        agent.client.search_products.return_value = [{"id": 20, "name": "Konsulenttime"}]
        agent.client.ensure_invoice_bank_account_number.return_value = {
            "id": 1920,
            "bankAccountNumber": "86011117947",
        }
        agent.client.create_order.return_value = {"id": 30, "orderDate": "2026-03-21"}
        agent.client.create_order_line.return_value = {"id": 40}
        agent.client.create_invoice.return_value = {
            "id": 50,
            "invoiceDate": "2026-03-21",
            "invoiceDueDate": "2026-03-21",
        }
        agent.client.search_invoices.return_value = [
            {
                "id": 50,
                "invoiceDate": "2026-03-21",
                "customer": {"id": 10, "name": "Acme AS"},
                "orders": [{"id": 30}],
            }
        ]

        result = agent._handle_create_invoice(
            {
                "customer_name": "Acme AS",
                "product_name": "Konsulenttime",
                "quantity": 2.0,
                "project_name": None,
            }
        )

        agent.client.create_order.assert_called_once_with(
            customer_id=10,
            order_date=None,
            project_id=None,
        )
        agent.client.create_order_line.assert_called_once_with(
            order_id=30,
            product_id=20,
            quantity=2.0,
            unit_price=None,
            description=None,
        )
        agent.client.create_invoice.assert_called_once_with(
            customer_id=10,
            order_id=30,
            invoice_date=None,
            invoice_due_date=None,
            send_to_customer=False,
        )
        self.assertEqual(result["message"], "Invoice created successfully")
        self.assertTrue(result["debug"]["verified"])
        self.assertEqual(result["debug"]["created_invoice_id"], 50)
        self.assertEqual(result["debug"]["invoice_bank_account_id"], 1920)
        self.assertEqual(result["debug"]["invoice_bank_account_number"], "86011117947")

    def test_handle_create_invoice_reports_bank_account_blocker(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_customers.return_value = [{"id": 10, "name": "Acme AS"}]
        agent.client.search_products.return_value = [{"id": 20, "name": "Konsulenttime"}]
        agent.client.ensure_invoice_bank_account_number.return_value = {
            "id": 1920,
            "bankAccountNumber": "86011117947",
        }
        agent.client.create_order.return_value = {"id": 30, "orderDate": "2026-03-21"}
        agent.client.create_order_line.return_value = {"id": 40}
        agent.client.create_invoice.side_effect = RuntimeError(
            'HTTP 422: Validering feilet. | developerMessage=VALIDATION_ERROR | '
            "validationMessages=[{'field': None, 'message': 'Faktura kan ikke opprettes før selskapet har registrert et bankkontonummer.'}]"
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "Tripletex company has no registered bank account number",
        ):
            agent._handle_create_invoice(
                {
                    "customer_name": "Acme AS",
                    "product_name": "Konsulenttime",
                    "quantity": 2.0,
                    "project_name": None,
                }
            )

    def test_handle_update_customer(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_customers.side_effect = [
            [{"id": 10, "name": "Acme AS", "email": "old@acme.no"}],
            [{"id": 10, "name": "Acme AS", "email": "post@acme.no"}],
        ]
        agent.client.update_customer.return_value = {
            "id": 10,
            "name": "Acme AS",
            "email": "post@acme.no",
        }

        result = agent._handle_update_customer(
            {
                "name": "Acme AS",
                "email": "post@acme.no",
            }
        )

        agent.client.update_customer.assert_called_once_with(
            customer_id=10,
            payload={"email": "post@acme.no"},
        )
        self.assertEqual(result["message"], "Customer updated successfully")
        self.assertTrue(result["debug"]["verified"])
        self.assertEqual(result["debug"]["updated_customer_email"], "post@acme.no")

    def test_handle_delete_product(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_products.side_effect = [
            [{"id": 20, "name": "Konsulenttime"}],
            [],
        ]
        agent.client.delete.return_value = {"status": "deleted"}

        result = agent._handle_delete_product({"name": "Konsulenttime"})

        agent.client.delete.assert_called_once_with("/product/20")
        self.assertEqual(result["message"], "Product deleted successfully")
        self.assertTrue(result["debug"]["verified"])
        self.assertEqual(result["debug"]["deleted_product_id"], 20)

    def test_handle_update_product(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_products.side_effect = [
            [{"id": 20, "name": "Konsulenttime", "description": "Gammel tekst"}],
            [{"id": 20, "name": "Konsulenttime", "description": "Oppdatert tekst"}],
        ]
        agent.client.update_product.return_value = {
            "id": 20,
            "name": "Konsulenttime",
            "description": "Oppdatert tekst",
        }

        result = agent._handle_update_product(
            {
                "name": "Konsulenttime",
                "description": "Oppdatert tekst",
            }
        )

        agent.client.update_product.assert_called_once_with(
            product_id=20,
            payload={"description": "Oppdatert tekst"},
        )
        self.assertEqual(result["message"], "Product updated successfully")
        self.assertTrue(result["debug"]["verified"])
        self.assertEqual(result["debug"]["updated_product_description"], "Oppdatert tekst")

    def test_handle_update_department(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_departments.side_effect = [
            [{"id": 55, "name": "Salg", "departmentNumber": "100"}],
            [{"id": 55, "name": "Salg", "departmentNumber": "202"}],
        ]
        agent.client.update_department.return_value = {
            "id": 55,
            "name": "Salg",
            "departmentNumber": "202",
        }

        result = agent._handle_update_department(
            {
                "name": "Salg",
                "department_number": "202",
            }
        )

        agent.client.update_department.assert_called_once_with(
            department_id=55,
            payload={"departmentNumber": "202"},
        )
        self.assertEqual(result["message"], "Department updated successfully")
        self.assertTrue(result["debug"]["verified"])
        self.assertEqual(result["debug"]["updated_department_number"], "202")

    def test_handle_delete_customer(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_customers.side_effect = [
            [{"id": 10, "name": "Acme AS", "email": "post@acme.no"}],
            [],
        ]
        agent.client.delete.return_value = {"status": "deleted"}

        result = agent._handle_delete_customer({"name": "Acme AS"})

        agent.client.delete.assert_called_once_with("/customer/10")
        self.assertEqual(result["message"], "Customer deleted successfully")
        self.assertTrue(result["debug"]["verified"])
        self.assertEqual(result["debug"]["deleted_customer_id"], 10)

    def test_handle_delete_department(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_departments.side_effect = [
            [{"id": 55, "name": "Salg", "departmentNumber": "202"}],
            [],
        ]
        agent.client.delete.return_value = {"status": "deleted"}

        result = agent._handle_delete_department({"name": "Salg"})

        agent.client.delete.assert_called_once_with("/department/55")
        self.assertEqual(result["message"], "Department deleted successfully")
        self.assertTrue(result["debug"]["verified"])
        self.assertEqual(result["debug"]["deleted_department_id"], 55)

    def test_handle_update_project(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_projects.side_effect = [
            [{"id": 70, "name": "Alpha", "customer": {"id": 10, "name": "Old AS"}}],
            [{"id": 70, "name": "Alpha", "customer": {"id": 11, "name": "Beta AS"}}],
        ]
        agent.client.search_customers.return_value = [{"id": 11, "name": "Beta AS"}]
        agent.client.update_project.return_value = {
            "id": 70,
            "name": "Alpha",
            "customer": {"id": 11, "name": "Beta AS"},
        }

        result = agent._handle_update_project(
            {
                "name": "Alpha",
                "customer_name": "Beta AS",
            }
        )

        agent.client.update_project.assert_called_once_with(
            project_id=70,
            payload={"customer": {"id": 11}},
        )
        self.assertEqual(result["message"], "Project updated successfully")
        self.assertTrue(result["debug"]["verified"])
        self.assertEqual(result["debug"]["linked_customer_name"], "Beta AS")

    def test_handle_delete_project(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_projects.side_effect = [
            [{"id": 70, "name": "Alpha", "customer": {"id": 11, "name": "Beta AS"}}],
            [],
        ]
        agent.client.delete.return_value = {"status": "deleted"}

        result = agent._handle_delete_project({"name": "Alpha"})

        agent.client.delete.assert_called_once_with("/project/70")
        self.assertEqual(result["message"], "Project deleted successfully")
        self.assertTrue(result["debug"]["verified"])
        self.assertEqual(result["debug"]["deleted_project_id"], 70)
        self.assertTrue(result["debug"]["beta_endpoint"])

    def test_handle_create_travel_expense(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.get_default_employee.return_value = {"id": 99}
        agent.client.create_travel_expense.return_value = {
            "id": 500,
            "title": "Oslo tur mars",
            "state": "OPEN",
        }
        agent.client.search_travel_expenses.return_value = [
            {"id": 500, "title": "Oslo tur mars", "state": "OPEN"}
        ]

        result = agent._handle_create_travel_expense({"title": "Oslo tur mars"})

        agent.client.create_travel_expense.assert_called_once_with(
            employee_id=99,
            title="Oslo tur mars",
        )
        self.assertEqual(result["message"], "Travel expense created successfully")
        self.assertTrue(result["debug"]["verified"])
        self.assertEqual(result["debug"]["created_travel_expense_id"], 500)

    def test_handle_delete_travel_expense(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.get_default_employee.return_value = {"id": 99}
        agent.client.search_travel_expenses.side_effect = [
            [{"id": 500, "title": "Oslo tur mars", "state": "OPEN"}],
            [],
        ]
        agent.client.delete.return_value = {"status": "deleted"}

        result = agent._handle_delete_travel_expense({"title": "Oslo tur mars"})

        agent.client.delete.assert_called_once_with("/travelExpense/500")
        self.assertEqual(result["message"], "Travel expense deleted successfully")
        self.assertTrue(result["debug"]["verified"])
        self.assertEqual(result["debug"]["deleted_travel_expense_id"], 500)

    def test_handle_update_travel_expense(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.get_default_employee.return_value = {"id": 99}
        agent.client.search_travel_expenses.side_effect = [
            [{"id": 500, "title": "Oslo tur mars", "state": "OPEN"}],
            [{"id": 500, "title": "Bergen tur mars", "state": "OPEN"}],
        ]
        agent.client.update_travel_expense.return_value = {
            "id": 500,
            "title": "Bergen tur mars",
            "state": "OPEN",
        }

        result = agent._handle_update_travel_expense(
            {"title": "Oslo tur mars", "updated_title": "Bergen tur mars"}
        )

        agent.client.update_travel_expense.assert_called_once_with(
            travel_expense_id=500,
            payload={"title": "Bergen tur mars"},
        )
        self.assertEqual(result["message"], "Travel expense updated successfully")
        self.assertTrue(result["debug"]["verified"])
        self.assertEqual(result["debug"]["updated_travel_expense_title"], "Bergen tur mars")

    def test_handle_delete_order(self) -> None:
        agent = TripletexAgent(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        agent.client = MagicMock()
        agent.client.search_customers.return_value = [{"id": 10, "name": "Acme AS"}]
        agent.client.search_products.return_value = [{"id": 20, "name": "Konsulenttime"}]
        agent.client.search_orders.side_effect = [
            [{"id": 30, "customer": {"id": 10, "name": "Acme AS"}}],
            [],
        ]
        agent.client.search_order_lines.return_value = [
            {"id": 40, "product": {"id": 20, "name": "Konsulenttime"}}
        ]
        agent.client.delete.return_value = {"status": "deleted"}

        result = agent._handle_delete_order(
            {
                "customer_name": "Acme AS",
                "product_name": "Konsulenttime",
            }
        )

        agent.client.delete.assert_called_once_with("/order/30")
        self.assertEqual(result["message"], "Order deleted successfully")
        self.assertTrue(result["debug"]["verified"])
        self.assertEqual(result["debug"]["deleted_order_id"], 30)

    @patch("tripletex_client.requests.request")
    def test_create_order_sends_delivery_date(self, mock_request: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": {"id": 30, "orderDate": "2026-03-21"}}
        mock_request.return_value = mock_response

        client = TripletexClient(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        client.create_order(customer_id=10)

        _, kwargs = mock_request.call_args
        self.assertIn("deliveryDate", kwargs["json"])
        self.assertEqual(kwargs["json"]["orderDate"], kwargs["json"]["deliveryDate"])

    @patch("tripletex_client.requests.request")
    def test_create_invoice_sends_query_params(self, mock_request: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.status_code = 200
        mock_response.json.return_value = {"value": {"id": 50}}
        mock_request.return_value = mock_response

        client = TripletexClient(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        client.create_invoice(
            customer_id=10,
            order_id=30,
            send_to_customer=False,
        )

        _, kwargs = mock_request.call_args
        self.assertEqual(kwargs["params"], {"sendToCustomer": "false"})

    @patch("tripletex_client.subprocess.run")
    @patch("tripletex_client.requests.request")
    def test_get_falls_back_to_curl_on_dns_failure(
        self,
        mock_request: MagicMock,
        mock_subprocess_run: MagicMock,
    ) -> None:
        mock_request.side_effect = requests.exceptions.ConnectionError(
            "Failed to resolve host: kkpqfuj-amager.tripletex.dev"
        )
        mock_subprocess_run.return_value = MagicMock(
            returncode=0,
            stdout='{"values":[{"id":1,"name":"Acme AS"}]}\n__TRIPLETEX_HTTP_STATUS__:200',
            stderr="",
        )

        client = TripletexClient(
            base_url="https://kkpqfuj-amager.tripletex.dev/v2",
            session_token="dummy-token",
        )

        result = client.get("/customer", params={"name": "Acme AS"})

        self.assertEqual(result["values"][0]["name"], "Acme AS")
        command = mock_subprocess_run.call_args.args[0]
        self.assertEqual(command[0], "curl")
        self.assertIn("https://kkpqfuj-amager.tripletex.dev/v2/customer?name=Acme+AS", command)

    @patch("tripletex_client.subprocess.run")
    @patch("tripletex_client.requests.request")
    def test_delete_falls_back_to_curl_on_dns_failure(
        self,
        mock_request: MagicMock,
        mock_subprocess_run: MagicMock,
    ) -> None:
        mock_request.side_effect = requests.exceptions.ConnectionError(
            "nodename nor servname provided, or not known"
        )
        mock_subprocess_run.return_value = MagicMock(
            returncode=0,
            stdout="\n__TRIPLETEX_HTTP_STATUS__:204",
            stderr="",
        )

        client = TripletexClient(
            base_url="https://kkpqfuj-amager.tripletex.dev/v2",
            session_token="dummy-token",
        )

        result = client.delete("/customer/10")

        self.assertEqual(result, {"status": "deleted"})

    def test_ensure_invoice_bank_account_number_updates_when_missing(self) -> None:
        client = TripletexClient(
            base_url="https://example.test/v2",
            session_token="dummy-token",
        )
        client.get_invoice_bank_account = MagicMock(
            return_value={"id": 1920, "bankAccountNumber": ""}
        )
        client.update_ledger_account = MagicMock(
            return_value={"id": 1920, "bankAccountNumber": "86011117947"}
        )

        result = client.ensure_invoice_bank_account_number()

        client.update_ledger_account.assert_called_once_with(
            account_id=1920,
            payload={"bankAccountNumber": "86011117947"},
        )
        self.assertEqual(result["bankAccountNumber"], "86011117947")


if __name__ == "__main__":
    unittest.main()
