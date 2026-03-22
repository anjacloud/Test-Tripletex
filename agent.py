import base64
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from schemas import SolveRequest
from tripletex_client import TripletexClient


@dataclass
class PlanStep:
    name: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    task_type: str
    extracted: Dict[str, Any] = field(default_factory=dict)
    steps: List[PlanStep] = field(default_factory=list)
    attachment_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SavedAttachment:
    filename: str
    path: str
    mime_type: str | None = None


class TripletexAgent:
    def __init__(self, base_url: str, session_token: str) -> None:
        self.client = TripletexClient(base_url=base_url, session_token=session_token)

    def _normalize_prompt(self, prompt: str) -> str:
        normalized = " ".join(prompt.strip().split())

        replacements = [
            (r"\banalysez\b", "analyze"),
            (r"\banalyser\b", "analyze"),
            (r"\banalyze\b", "analyze"),
            (r"\bidentifiez\b", "identify"),
            (r"\bidentifier\b", "identify"),
            (r"\bcréez\b", "create"),
            (r"\bmettre a jour\b", "update"),
            (r"\bmettre à jour\b", "update"),
            (r"\bissue\b", "create"),
            (r"\bpara customer\b", "for customer"),
            (r"\bpour customer\b", "for customer"),
            (r"\bcorreo electrónico\b", "email"),
            (r"\bcorreio eletrônico\b", "email"),
            (r"\bcorreio eletronico\b", "email"),
            (r"\bcourriel\b", "email"),
            (r"\be-?mail\b", "email"),
            (r"\bmit customer\b", "for customer"),
            (r"\bfür kunde\b", "for customer"),
            (r"\bfuer kunde\b", "for customer"),
            (r"\bpara cliente\b", "for customer"),
            (r"\bpour client\b", "for customer"),
            (r"\bpour customer\b", "for customer"),
            (r"\bpara projeto\b", "for project"),
            (r"\bpour projet\b", "for project"),
            (r"\bpara product\b", "with product"),
            (r"\bcon producto\b", "with product"),
            (r"\bcom produto\b", "with product"),
            (r"\bavec produit\b", "with product"),
            (r"\bmit produkt\b", "with product"),
            (r"\bmit product\b", "with product"),
            (r"\bcon email\b", "with email"),
            (r"\bavec email\b", "with email"),
            (r"\bcom email\b", "with email"),
            (r"\bmit email\b", "with email"),
            (r"\bavec description\b", "with description"),
            (r"\bcon descripcion\b", "with description"),
            (r"\bcon descripción\b", "with description"),
            (r"\bcom descricao\b", "with description"),
            (r"\bcom descrição\b", "with description"),
            (r"\bmit beschreibung\b", "with description"),
            (r"\bnúmero de departamento\b", "department number"),
            (r"\bnumero de departamento\b", "department number"),
            (r"\bnuméro de département\b", "department number"),
            (r"\bnumero de departement\b", "department number"),
            (r"\babteilungsnummer\b", "department number"),
            (r"\bcon department number\b", "with department number"),
            (r"\bcom department number\b", "with department number"),
            (r"\bavec department number\b", "with department number"),
            (r"\bmit nummer\b", "with number"),
            (r"\bcantidad\b", "quantity"),
            (r"\bquantidade\b", "quantity"),
            (r"\bquantité\b", "quantity"),
            (r"\bquantite\b", "quantity"),
            (r"\bmenge\b", "quantity"),
            (r"\bcréer\b", "create"),
            (r"\bcreer\b", "create"),
            (r"\bcrear\b", "create"),
            (r"\bcriar\b", "create"),
            (r"\bregistrar\b", "register"),
            (r"\berstelle\b", "create"),
            (r"\berstellen\b", "create"),
            (r"\blag\b", "create"),
            (r"\baktualisiere\b", "update"),
            (r"\baktualisieren\b", "update"),
            (r"\bactualizar\b", "update"),
            (r"\batualizar\b", "update"),
            (r"\bmettre\b", "set"),
            (r"\bsupprimer\b", "delete"),
            (r"\beliminar\b", "delete"),
            (r"\bborrar\b", "delete"),
            (r"\bexcluir\b", "delete"),
            (r"\bapagar\b", "delete"),
            (r"\blösche\b", "delete"),
            (r"\bloesche\b", "delete"),
            (r"\bpago\b", "payment"),
            (r"\bpagamento\b", "payment"),
            (r"\bpaiement\b", "payment"),
            (r"\bzahlung\b", "payment"),
            (r"\bnota de crédito\b", "credit note"),
            (r"\bnota de credito\b", "credit note"),
            (r"\bnota crédito\b", "credit note"),
            (r"\bnota credito\b", "credit note"),
            (r"\babono\b", "credit note"),
            (r"\bavoir\b", "credit note"),
            (r"\bgutschrift\b", "credit note"),
            (r"\bfacture d'avoir\b", "credit note"),
            (r"\blançamento\b", "voucher"),
            (r"\blancamento\b", "voucher"),
            (r"\bécriture\b", "voucher"),
            (r"\becriture\b", "voucher"),
            (r"\bbuchung\b", "voucher"),
            (r"\bkunde\b", "customer"),
            (r"\bcliente\b", "customer"),
            (r"\bclient\b", "customer"),
            (r"\bprodukt\b", "product"),
            (r"\bproducto\b", "product"),
            (r"\bproduto\b", "product"),
            (r"\bproduit\b", "product"),
            (r"\bavdeling\b", "department"),
            (r"\bdepartamento\b", "department"),
            (r"\bdépartement\b", "department"),
            (r"\bdepartement\b", "department"),
            (r"\babteilung\b", "department"),
            (r"\bprosjekt\b", "project"),
            (r"\bprojeto\b", "project"),
            (r"\bproyecto\b", "project"),
            (r"\bprojet\b", "project"),
            (r"projekt", "project"),
            (r"\borderre\b", "order"),
            (r"\bordre\b", "order"),
            (r"\bpedido\b", "order"),
            (r"\bcommande\b", "order"),
            (r"\bauftrag\b", "order"),
            (r"\bfaktura\b", "invoice"),
            (r"\bfatura\b", "invoice"),
            (r"\bfactura\b", "invoice"),
            (r"\bfacture\b", "invoice"),
            (r"\brechnung\b", "invoice"),
            (r"\bansatt\b", "employee"),
            (r"\bmedarbeider\b", "employee"),
            (r"\bempleado\b", "employee"),
            (r"\bfuncionário\b", "employee"),
            (r"\bfuncionario\b", "employee"),
            (r"\bemployé\b", "employee"),
            (r"\bemploye\b", "employee"),
            (r"\bmitarbeiter\b", "employee"),
            (r"\breiseregning\b", "travel expense"),
            (r"\bexpense report\b", "travel expense"),
            (r"\bnota de despesa\b", "travel expense"),
            (r"\binforme de gastos\b", "travel expense"),
            (r"\bnote de frais\b", "travel expense"),
            (r"\breisekostenabrechnung\b", "travel expense"),
            (r"\bactivité\b", "activity"),
            (r"\bactivite\b", "activity"),
            (r"\baktivitet\b", "activity"),
            (r"\baktivitaet\b", "activity"),
            (r"\bgrand livre\b", "general ledger"),
            (r"\bhovedbok\b", "general ledger"),
            (r"\bgroßbuch\b", "general ledger"),
            (r"\bgrossbuch\b", "general ledger"),
            (r"\bcompte de charge\b", "expense account"),
            (r"\bcomptes de charges\b", "expense accounts"),
            (r"\bcompte de charges\b", "expense account"),
            (r"\bexpense accounts\b", "expense account"),
            (r"\bcomptes\b", "accounts"),
            (r"\bcompte\b", "account"),
            (r"\bcharges\b", "expense"),
            (r"\bcoûts\b", "costs"),
            (r"\bcouts\b", "costs"),
            (r"\baugmenté\b", "increased"),
            (r"\baugmente\b", "increase"),
            (r"\baugmentation\b", "increase"),
            (r"\bjanvier\b", "january"),
            (r"\bfévrier\b", "february"),
            (r"\bfevrier\b", "february"),
            (r"\bavril\b", "april"),
            (r"\bmai\b", "may"),
            (r"\bjuin\b", "june"),
            (r"\bjuillet\b", "july"),
            (r"\baoût\b", "august"),
            (r"\baout\b", "august"),
            (r"\bseptembre\b", "september"),
            (r"\boctobre\b", "october"),
            (r"\bnovembre\b", "november"),
            (r"\bdécembre\b", "december"),
            (r"\bdecembre\b", "december"),
            (r"\binterne\b", "internal"),
            (r"\btrois\b", "3"),
            (r"\badministrator de konto\b", "account administrator"),
            (r"\badministrador de cuenta\b", "account administrator"),
            (r"\badministrador da conta\b", "account administrator"),
            (r"\badministrateur du compte\b", "account administrator"),
            (r"\badministrateur du account\b", "account administrator"),
            (r"\bkontoadministrator\b", "account administrator"),
        ]

        for pattern, replacement in replacements:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

        return " ".join(normalized.strip().split())

    async def solve(self, request: SolveRequest) -> dict[str, Any]:
        saved_files = self._save_files(request)
        normalized_prompt = self._normalize_prompt(request.prompt)
        plan: ExecutionPlan | None = None

        try:
            plan = self._build_plan(request.prompt)
            self._apply_attachment_context(plan, saved_files)

            result = self._execute_plan(plan)

            return {
                "status": "completed",
                "message": result.get("message", "Request handled"),
                "debug": {
                    "prompt": request.prompt,
                    "normalized_prompt": normalized_prompt,
                    "task_type": plan.task_type,
                    "plan_steps": [
                        {
                            "name": step.name,
                            "action": step.action,
                            "params": step.params,
                        }
                        for step in plan.steps
                    ],
                    "saved_files": [
                        {
                            "filename": attachment.filename,
                            "path": attachment.path,
                            "mime_type": attachment.mime_type,
                        }
                        for attachment in saved_files
                    ],
                    **result.get("debug", {}),
                },
            }

        except Exception as e:
            return {
                "status": "failed",
                "message": "Agent execution failed",
                "debug": {
                    "prompt": request.prompt,
                    "normalized_prompt": normalized_prompt,
                    "task_type": plan.task_type if plan else None,
                    "plan_steps": [
                        {
                            "name": step.name,
                            "action": step.action,
                            "params": step.params,
                        }
                        for step in (plan.steps if plan else [])
                    ],
                    "saved_files": [
                        {
                            "filename": attachment.filename,
                            "path": attachment.path,
                            "mime_type": attachment.mime_type,
                        }
                        for attachment in saved_files
                    ],
                    "error": str(e),
                },
            }

    def _build_plan(self, prompt: str) -> ExecutionPlan:
        task_type = self._classify_prompt(prompt)
        extracted = self._extract_fields(prompt, task_type)

        plan = ExecutionPlan(
            task_type=task_type,
            extracted=extracted,
            steps=[],
        )

        if task_type == "customer_create":
            plan.steps.append(
                PlanStep(
                    name="create_customer",
                    action="customer_create",
                    params=extracted,
                )
            )

        elif task_type == "customer_update":
            plan.steps.append(
                PlanStep(
                    name="update_customer",
                    action="customer_update",
                    params=extracted,
                )
            )

        elif task_type == "customer_delete":
            plan.steps.append(
                PlanStep(
                    name="delete_customer",
                    action="customer_delete",
                    params=extracted,
                )
            )

        elif task_type == "product_create":
            plan.steps.append(
                PlanStep(
                    name="create_product",
                    action="product_create",
                    params=extracted,
                )
            )

        elif task_type == "product_update":
            plan.steps.append(
                PlanStep(
                    name="update_product",
                    action="product_update",
                    params=extracted,
                )
            )

        elif task_type == "product_delete":
            plan.steps.append(
                PlanStep(
                    name="delete_product",
                    action="product_delete",
                    params=extracted,
                )
            )

        elif task_type == "department_create":
            plan.steps.append(
                PlanStep(
                    name="create_department",
                    action="department_create",
                    params=extracted,
                )
            )

        elif task_type == "department_update":
            plan.steps.append(
                PlanStep(
                    name="update_department",
                    action="department_update",
                    params=extracted,
                )
            )

        elif task_type == "department_delete":
            plan.steps.append(
                PlanStep(
                    name="delete_department",
                    action="department_delete",
                    params=extracted,
                )
            )

        elif task_type == "project_create":
            plan.steps.append(
                PlanStep(
                    name="create_project",
                    action="project_create",
                    params=extracted,
                )
            )

        elif task_type == "project_update":
            plan.steps.append(
                PlanStep(
                    name="update_project",
                    action="project_update",
                    params=extracted,
                )
            )

        elif task_type == "project_delete":
            plan.steps.append(
                PlanStep(
                    name="delete_project",
                    action="project_delete",
                    params=extracted,
                )
            )

        elif task_type == "travel_expense_create":
            plan.steps.append(
                PlanStep(
                    name="create_travel_expense",
                    action="travel_expense_create",
                    params=extracted,
                )
            )

        elif task_type == "travel_expense_update":
            plan.steps.append(
                PlanStep(
                    name="update_travel_expense",
                    action="travel_expense_update",
                    params=extracted,
                )
            )

        elif task_type == "travel_expense_delete":
            plan.steps.append(
                PlanStep(
                    name="delete_travel_expense",
                    action="travel_expense_delete",
                    params=extracted,
                )
            )

        elif task_type == "order_create":
            plan.steps.append(
                PlanStep(
                    name="create_order",
                    action="order_create",
                    params=extracted,
                )
            )

        elif task_type == "order_delete":
            plan.steps.append(
                PlanStep(
                    name="delete_order",
                    action="order_delete",
                    params=extracted,
                )
            )

        elif task_type == "invoice_create":
            plan.steps.append(
                PlanStep(
                    name="create_invoice",
                    action="invoice_create",
                    params=extracted,
                )
            )

        elif task_type == "employee_create":
            plan.steps.append(
                PlanStep(
                    name="create_employee",
                    action="employee_create",
                    params=extracted,
                )
            )

        elif task_type in {
            "invoice_delete",
            "invoice_update",
            "order_update",
            "employee_update",
            "employee_delete",
            "payment_unsupported",
            "credit_note_unsupported",
            "voucher_unsupported",
            "ledger_analysis_unsupported",
        }:
            plan.steps.append(
                PlanStep(
                    name=f"unsupported_{task_type}",
                    action=task_type,
                    params=extracted,
                )
            )

        else:
            plan.steps.append(
                PlanStep(
                    name="unknown_task",
                    action="unknown",
                    params={"prompt": prompt},
                )
            )

        return plan

    def _execute_plan(self, plan: ExecutionPlan) -> Dict[str, Any]:
        result: Optional[Dict[str, Any]] = None

        for step in plan.steps:
            if step.action == "customer_create":
                result = self._handle_create_customer(step.params)

            elif step.action == "customer_update":
                result = self._handle_update_customer(step.params)

            elif step.action == "customer_delete":
                result = self._handle_delete_customer(step.params)

            elif step.action == "product_create":
                result = self._handle_create_product(step.params)

            elif step.action == "product_update":
                result = self._handle_update_product(step.params)

            elif step.action == "product_delete":
                result = self._handle_delete_product(step.params)

            elif step.action == "department_create":
                result = self._handle_create_department(step.params)

            elif step.action == "department_update":
                result = self._handle_update_department(step.params)

            elif step.action == "department_delete":
                result = self._handle_delete_department(step.params)

            elif step.action == "project_create":
                result = self._handle_create_project(step.params)

            elif step.action == "project_update":
                result = self._handle_update_project(step.params)

            elif step.action == "project_delete":
                result = self._handle_delete_project(step.params)

            elif step.action == "travel_expense_create":
                result = self._handle_create_travel_expense(step.params)

            elif step.action == "travel_expense_update":
                result = self._handle_update_travel_expense(step.params)

            elif step.action == "travel_expense_delete":
                result = self._handle_delete_travel_expense(step.params)

            elif step.action == "order_create":
                result = self._handle_create_order(step.params)

            elif step.action == "order_delete":
                result = self._handle_delete_order(step.params)

            elif step.action == "invoice_create":
                result = self._handle_create_invoice(step.params)

            elif step.action == "employee_create_paused":
                result = {
                    "message": "Employee creation not implemented safely yet",
                    "debug": {
                        "reason": "employee workflow is paused until roles/userCategory flow is implemented",
                        "parsed_fields": step.params,
                    },
                }

            elif step.action == "employee_create":
                result = self._handle_create_employee(step.params)

            elif step.action == "invoice_delete":
                result = self._unsupported_response(
                    "Invoice deletion is not implemented; invoices should not be deleted by this agent yet",
                    task_type=plan.task_type,
                )

            elif step.action == "invoice_update":
                result = self._unsupported_response(
                    "Invoice update workflows are not implemented yet",
                    task_type=plan.task_type,
                )

            elif step.action == "order_update":
                result = self._unsupported_response(
                    "Order update workflows are not implemented yet",
                    task_type=plan.task_type,
                )

            elif step.action == "employee_update":
                result = self._unsupported_response(
                    "Employee update workflows are not implemented yet",
                    task_type=plan.task_type,
                )

            elif step.action == "employee_delete":
                result = self._unsupported_response(
                    "Employee deletion workflows are not implemented yet",
                    task_type=plan.task_type,
                )

            elif step.action == "payment_unsupported":
                result = self._unsupported_response(
                    "Payment workflows are not implemented yet",
                    task_type=plan.task_type,
                )

            elif step.action == "credit_note_unsupported":
                result = self._unsupported_response(
                    "Credit note workflows are not implemented yet",
                    task_type=plan.task_type,
                )

            elif step.action == "voucher_unsupported":
                result = self._unsupported_response(
                    "Voucher workflows are not implemented yet",
                    task_type=plan.task_type,
                )

            elif step.action == "ledger_analysis_unsupported":
                result = self._unsupported_response(
                    (
                        "Ledger-analysis workflows with follow-up project/activity creation "
                        "are not implemented yet"
                    ),
                    task_type=plan.task_type,
                    extra_debug={"parsed_fields": step.params},
                )

            else:
                result = self._unsupported_response(
                    f"Unsupported task type: {plan.task_type}",
                    task_type=plan.task_type,
                )

        return result or self._unsupported_response("No plan steps executed")

    def _apply_attachment_context(
        self,
        plan: ExecutionPlan,
        saved_files: List[SavedAttachment],
    ) -> None:
        if not saved_files:
            return

        if plan.task_type == "travel_expense_create":
            title = plan.extracted.get("title")
            if not self._travel_expense_title_needs_attachment_fallback(title):
                return

            derived_title = self._derive_title_from_attachment(saved_files[0])
            if not derived_title:
                return

            plan.extracted["title"] = derived_title
            plan.attachment_context = {
                "used_for": "travel_expense_title",
                "source_filename": saved_files[0].filename,
                "derived_title": derived_title,
            }
            for step in plan.steps:
                step.params["title"] = derived_title
                step.params["attachment_context"] = plan.attachment_context
            return

        if plan.task_type != "customer_create":
            return

        customer_name = plan.extracted.get("name")
        customer_email = plan.extracted.get("email")
        if customer_name and not self._customer_name_needs_attachment_fallback(customer_name):
            normalized_customer_name = customer_name
        else:
            normalized_customer_name = None

        if normalized_customer_name and customer_email:
            return

        attachment_text = self._read_attachment_text(saved_files[0])
        if not attachment_text:
            return

        derived_name = normalized_customer_name or self._extract_attachment_labeled_value(
            attachment_text,
            [
                "customer",
                "customer name",
                "kunde",
                "client",
                "cliente",
                "name",
                "navn",
            ],
        )
        derived_email = customer_email or self._extract_email_from_text(attachment_text)
        if not derived_name and not derived_email:
            return

        if derived_name:
            plan.extracted["name"] = derived_name
        if derived_email:
            plan.extracted["email"] = derived_email
        plan.attachment_context = {
            "used_for": "customer_create_fields",
            "source_filename": saved_files[0].filename,
            "derived_name": derived_name,
            "derived_email": derived_email,
        }
        for step in plan.steps:
            if derived_name:
                step.params["name"] = derived_name
            if derived_email:
                step.params["email"] = derived_email
            step.params["attachment_context"] = plan.attachment_context

    def _travel_expense_title_needs_attachment_fallback(
        self,
        title: str | None,
    ) -> bool:
        if not title:
            return True

        normalized_title = re.sub(r"\s+", " ", title.strip().lower())
        normalized_title = re.sub(r"^(from|fra)\s+", "", normalized_title)

        generic_patterns = [
            r"(?:the\s+)?attached\s+(?:receipt|file|pdf)",
            r"(?:an?\s+)?attachment",
            r"(?:the\s+)?receipt",
            r"(?:vedlagt|vedlagte)\s+(?:kvittering|fil|pdf)",
            r"kvittering(?:en)?",
        ]
        return any(
            re.fullmatch(pattern, normalized_title, flags=re.IGNORECASE)
            for pattern in generic_patterns
        )

    def _derive_title_from_attachment(self, attachment: SavedAttachment) -> str | None:
        stem = Path(attachment.filename).stem.strip()
        if not stem:
            return None
        cleaned = re.sub(r"[_\-]+", " ", stem)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned or None

    def _customer_name_needs_attachment_fallback(self, name: str | None) -> bool:
        if not name:
            return True

        normalized_name = re.sub(r"\s+", " ", name.strip().lower())
        generic_patterns = [
            r"(?:from|fra)\s+(?:attached|vedlagt)\s+(?:file|attachment|pdf|receipt|kvittering)",
            r"(?:the\s+)?attached\s+(?:file|attachment|pdf|receipt)",
            r"(?:the\s+)?attachment",
            r"(?:the\s+)?receipt",
        ]
        return any(
            re.fullmatch(pattern, normalized_name, flags=re.IGNORECASE)
            for pattern in generic_patterns
        )

    def _read_attachment_text(self, attachment: SavedAttachment) -> str | None:
        try:
            data = Path(attachment.path).read_bytes()
        except OSError:
            return None

        if not data:
            return None

        printable_bytes = sum(
            1 for byte in data if byte in b"\t\n\r" or 32 <= byte <= 126 or byte >= 160
        )
        if (printable_bytes / len(data)) < 0.85:
            return None

        for encoding in ("utf-8", "latin-1"):
            try:
                text = data.decode(encoding).strip()
            except UnicodeDecodeError:
                continue
            if text:
                return text

        return None

    def _extract_attachment_labeled_value(
        self,
        text: str,
        labels: List[str],
    ) -> str | None:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line in lines:
            for label in labels:
                match = re.search(
                    rf"^{re.escape(label)}\s*[:=-]\s*(.+)$",
                    line,
                    flags=re.IGNORECASE,
                )
                if match:
                    return match.group(1).strip()
        return None

    def _extract_email_from_text(self, text: str) -> str | None:
        match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        return match.group(0) if match else None

    def _unsupported_response(
        self,
        message: str,
        task_type: str | None = None,
        extra_debug: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        debug = {
            "implemented": False,
            "unsupported": True,
            "unsupported_task_type": task_type,
        }
        if extra_debug:
            debug.update(extra_debug)
        return {
            "message": message,
            "debug": debug,
        }

    def _has_account_administrator_entitlement(
        self,
        entitlements: List[Dict[str, Any]],
    ) -> bool:
        admin_entitlements = {
            "ROLE_ADMINISTRATOR",
            "AUTH_COMPANY_ADMIN",
        }
        entitlement_names = {str(item.get("name", "")) for item in entitlements}
        return not admin_entitlements.isdisjoint(entitlement_names)

    def _is_invoice_bank_account_blocker(self, message: str) -> bool:
        lowered = message.lower()
        return "bankkontonummer" in lowered or "bank account" in lowered

    def _contains_any_term(self, text: str, terms: List[str]) -> bool:
        return any(
            re.search(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE)
            for term in terms
        )

    def _extract_fields(self, prompt: str, task_type: str) -> Dict[str, Any]:
        prompt = self._normalize_prompt(prompt)

        if task_type == "customer_create":
            return self._extract_customer_fields(prompt)

        if task_type == "customer_update":
            return self._extract_customer_update_fields(prompt)

        if task_type == "customer_delete":
            return self._extract_customer_delete_fields(prompt)

        if task_type == "product_create":
            return self._extract_product_fields(prompt)

        if task_type == "product_update":
            return self._extract_product_update_fields(prompt)

        if task_type == "product_delete":
            return self._extract_product_delete_fields(prompt)

        if task_type == "department_create":
            return self._extract_department_fields(prompt)

        if task_type == "department_update":
            return self._extract_department_update_fields(prompt)

        if task_type == "department_delete":
            return self._extract_department_delete_fields(prompt)

        if task_type == "employee_create":
            return self._extract_employee_fields(prompt)

        if task_type == "project_create":
            return self._extract_project_fields(prompt)

        if task_type == "project_update":
            return self._extract_project_update_fields(prompt)

        if task_type == "project_delete":
            return self._extract_project_delete_fields(prompt)

        if task_type == "travel_expense_create":
            return self._extract_travel_expense_fields(prompt)

        if task_type == "travel_expense_update":
            return self._extract_travel_expense_update_fields(prompt)

        if task_type == "travel_expense_delete":
            return self._extract_travel_expense_delete_fields(prompt)

        if task_type == "order_create":
            return self._extract_order_fields(prompt)

        if task_type == "order_delete":
            return self._extract_order_delete_fields(prompt)

        if task_type == "invoice_create":
            return self._extract_invoice_fields(prompt)

        if task_type == "ledger_analysis_unsupported":
            return self._extract_ledger_analysis_fields(prompt)

        return {"prompt": prompt}

    def _extract_ledger_analysis_fields(self, prompt: str) -> Dict[str, Any]:
        normalized = " ".join(prompt.strip().split())
        month_names = (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        )
        month_pattern = "|".join(month_names)

        months = re.findall(rf"\b({month_pattern})\b", normalized, flags=re.IGNORECASE)
        years = re.findall(r"\b(20\d{2})\b", normalized)
        top_n_match = re.search(
            r"\b(\d+)\s+(?:expense\s+)?accounts?\b",
            normalized,
            flags=re.IGNORECASE,
        )
        if not top_n_match:
            top_n_match = re.search(
                r"\bidentify\s+(?:the\s+)?(\d+)\b",
                normalized,
                flags=re.IGNORECASE,
            )

        return {
            "prompt": normalized,
            "period_months": [month.lower() for month in months[:2]],
            "period_year": years[0] if years else None,
            "top_n": int(top_n_match.group(1)) if top_n_match else None,
            "requested_actions": {
                "analyze_general_ledger": "general ledger" in normalized.lower(),
                "identify_expense_accounts": "expense account" in normalized.lower(),
                "create_projects": "project" in normalized.lower() and "create" in normalized.lower(),
                "create_activities": "activity" in normalized.lower() and "create" in normalized.lower(),
            },
        }

    def _resolve_customer_id(self, customer_name: str) -> int:
        matches = self.client.search_customers(customer_name, count=10)
        exact = next((c for c in matches if c.get("name") == customer_name), None)

        if not exact or not exact.get("id"):
            raise RuntimeError(f'Customer "{customer_name}" was not found')

        return int(exact["id"])

    def _resolve_product_id(self, product_name: str) -> int:
        matches = self.client.search_products(product_name, count=10)
        exact = next((p for p in matches if p.get("name") == product_name), None)

        if not exact or not exact.get("id"):
            raise RuntimeError(f'Product "{product_name}" was not found')

        return int(exact["id"])

    def _resolve_project_id(self, project_name: str) -> int:
        matches = self.client.search_projects(project_name, count=20)
        exact = next((p for p in matches if p.get("name") == project_name), None)

        if not exact or not exact.get("id"):
            raise RuntimeError(f'Project "{project_name}" was not found')

        return int(exact["id"])

    def _handle_create_customer(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        if not parsed.get("name"):
            raise RuntimeError("Could not extract customer name from prompt")

        existing_matches = self.client.search_customers(parsed["name"], count=10)

        exact_existing = next(
            (c for c in existing_matches if c.get("name") == parsed["name"]),
            None,
        )

        if exact_existing:
            return {
                "message": "Customer already exists",
                "debug": {
                    "created_customer_id": exact_existing.get("id"),
                    "created_customer_name": exact_existing.get("name"),
                    "created_customer_email": exact_existing.get("email"),
                    "attachment_context": parsed.get("attachment_context"),
                    "verified": True,
                    "reused_existing": True,
                },
            }

        created = self.client.create_customer(
            name=parsed["name"],
            email=parsed["email"],
        )

        matches = self.client.search_customers(parsed["name"], count=10)

        verified = any(
            c.get("id") == created.get("id") and c.get("name") == parsed["name"]
            for c in matches
        )

        return {
            "message": "Customer created successfully",
            "debug": {
                "created_customer_id": created.get("id"),
                "created_customer_name": created.get("name"),
                "created_customer_email": created.get("email"),
                "attachment_context": parsed.get("attachment_context"),
                "verified": verified,
                "reused_existing": False,
            },
        }

    def _handle_update_customer(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        customer_name = parsed.get("name")
        email = parsed.get("email")

        if not customer_name:
            raise RuntimeError("Could not extract customer name from prompt")
        if not email:
            raise RuntimeError("Could not extract updated customer email from prompt")

        existing_matches = self.client.search_customers(customer_name, count=20)
        exact_existing = next(
            (customer for customer in existing_matches if customer.get("name") == customer_name),
            None,
        )

        if not exact_existing or not exact_existing.get("id"):
            raise RuntimeError(f'Customer "{customer_name}" was not found')

        customer_id = int(exact_existing["id"])

        updated = self.client.update_customer(
            customer_id=customer_id,
            payload={"email": email},
        )

        verified_matches = self.client.search_customers(customer_name, count=20)
        verified_customer = next(
            (
                customer
                for customer in verified_matches
                if customer.get("id") == customer_id
                and customer.get("name") == customer_name
            ),
            None,
        )

        verified = verified_customer is not None and verified_customer.get("email") == email

        return {
            "message": "Customer updated successfully",
            "debug": {
                "updated_customer_id": customer_id,
                "updated_customer_name": customer_name,
                "updated_customer_email": (verified_customer or updated).get("email") or email,
                "verified": verified,
            },
        }

    def _handle_delete_customer(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        customer_name = parsed.get("name")

        if not customer_name:
            raise RuntimeError("Could not extract customer name from prompt")

        existing_matches = self.client.search_customers(customer_name, count=20)
        exact_existing = next(
            (customer for customer in existing_matches if customer.get("name") == customer_name),
            None,
        )

        if not exact_existing or not exact_existing.get("id"):
            raise RuntimeError(f'Customer "{customer_name}" was not found')

        customer_id = int(exact_existing["id"])
        delete_result = self.client.delete(f"/customer/{customer_id}")

        verified_matches = self.client.search_customers(customer_name, count=20)
        verified_deleted = not any(
            customer.get("id") == customer_id for customer in verified_matches
        )

        return {
            "message": "Customer deleted successfully",
            "debug": {
                "deleted_customer_id": customer_id,
                "deleted_customer_name": customer_name,
                "delete_result": delete_result,
                "verified": verified_deleted,
            },
        }

    def _handle_create_product(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        if not parsed.get("name"):
            raise RuntimeError("Could not extract product name from prompt")

        existing_matches = self.client.search_products(parsed["name"], count=10)

        exact_existing = next(
            (p for p in existing_matches if p.get("name") == parsed["name"]),
            None,
        )

        if exact_existing:
            return {
                "message": "Product already exists",
                "debug": {
                    "created_product_id": exact_existing.get("id"),
                    "created_product_name": exact_existing.get("name"),
                    "created_product_description": exact_existing.get("description"),
                    "verified": True,
                    "reused_existing": True,
                },
            }

        created = self.client.create_product(
            name=parsed["name"],
            description=parsed["description"],
        )

        matches = self.client.search_products(parsed["name"], count=10)

        verified = any(
            p.get("id") == created.get("id") and p.get("name") == parsed["name"]
            for p in matches
        )

        return {
            "message": "Product created successfully",
            "debug": {
                "created_product_id": created.get("id"),
                "created_product_name": created.get("name"),
                "created_product_description": created.get("description"),
                "verified": verified,
                "reused_existing": False,
            },
        }

    def _handle_update_product(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        product_name = parsed.get("name")
        description = parsed.get("description")

        if not product_name:
            raise RuntimeError("Could not extract product name from prompt")
        if not description:
            raise RuntimeError("Could not extract updated product description from prompt")

        existing_matches = self.client.search_products(product_name, count=20)
        exact_existing = next(
            (product for product in existing_matches if product.get("name") == product_name),
            None,
        )

        if not exact_existing or not exact_existing.get("id"):
            raise RuntimeError(f'Product "{product_name}" was not found')

        product_id = int(exact_existing["id"])

        updated = self.client.update_product(
            product_id=product_id,
            payload={"description": description},
        )

        verified_matches = self.client.search_products(product_name, count=20)
        verified_product = next(
            (
                product
                for product in verified_matches
                if product.get("id") == product_id
                and product.get("name") == product_name
            ),
            None,
        )

        verified = (
            verified_product is not None
            and verified_product.get("description") == description
        )

        return {
            "message": "Product updated successfully",
            "debug": {
                "updated_product_id": product_id,
                "updated_product_name": product_name,
                "updated_product_description": (
                    (verified_product or updated).get("description") or description
                ),
                "verified": verified,
            },
        }

    def _handle_delete_product(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        product_name = parsed.get("name")

        if not product_name:
            raise RuntimeError("Could not extract product name from prompt")

        existing_matches = self.client.search_products(product_name, count=20)
        exact_existing = next(
            (product for product in existing_matches if product.get("name") == product_name),
            None,
        )

        if not exact_existing or not exact_existing.get("id"):
            raise RuntimeError(f'Product "{product_name}" was not found')

        product_id = int(exact_existing["id"])
        delete_result = self.client.delete(f"/product/{product_id}")

        verified_matches = self.client.search_products(product_name, count=20)
        verified_deleted = not any(
            product.get("id") == product_id for product in verified_matches
        )

        return {
            "message": "Product deleted successfully",
            "debug": {
                "deleted_product_id": product_id,
                "deleted_product_name": product_name,
                "delete_result": delete_result,
                "verified": verified_deleted,
            },
        }

    def _handle_create_department(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        if not parsed.get("name"):
            raise RuntimeError("Could not extract department name from prompt")

        existing_matches = self.client.search_departments(
            name=parsed["name"],
            department_number=parsed["department_number"],
            count=20,
        )

        exact_existing = next(
            (
                m
                for m in existing_matches
                if m.get("name") == parsed["name"]
                and (
                    parsed["department_number"] is None
                    or str(m.get("departmentNumber")) == str(parsed["department_number"])
                )
            ),
            None,
        )

        if exact_existing:
            return {
                "message": "Department already exists",
                "debug": {
                    "created_department_id": exact_existing.get("id"),
                    "created_department_name": exact_existing.get("name"),
                    "created_department_number": exact_existing.get("departmentNumber"),
                    "verified": True,
                    "reused_existing": True,
                },
            }

        created = self.client.create_department(
            name=parsed["name"],
            department_number=parsed["department_number"],
        )

        matches = self.client.search_departments(
            name=parsed["name"],
            department_number=parsed["department_number"],
            count=20,
        )

        verified = any(
            m.get("id") == created.get("id") and m.get("name") == parsed["name"]
            for m in matches
        )

        return {
            "message": "Department created successfully",
            "debug": {
                "created_department_id": created.get("id"),
                "created_department_name": created.get("name"),
                "created_department_number": created.get("departmentNumber"),
                "verified": verified,
                "reused_existing": False,
            },
        }

    def _handle_update_department(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        department_name = parsed.get("name")
        department_number = parsed.get("department_number")

        if not department_name:
            raise RuntimeError("Could not extract department name from prompt")
        if not department_number:
            raise RuntimeError("Could not extract updated department number from prompt")

        existing_matches = self.client.search_departments(
            name=department_name,
            count=20,
        )
        exact_existing = next(
            (
                department
                for department in existing_matches
                if department.get("name") == department_name
            ),
            None,
        )

        if not exact_existing or not exact_existing.get("id"):
            raise RuntimeError(f'Department "{department_name}" was not found')

        department_id = int(exact_existing["id"])
        updated = self.client.update_department(
            department_id=department_id,
            payload={"departmentNumber": department_number},
        )

        verified_matches = self.client.search_departments(
            name=department_name,
            department_number=department_number,
            count=20,
        )
        verified_department = next(
            (
                department
                for department in verified_matches
                if department.get("id") == department_id
                and department.get("name") == department_name
            ),
            None,
        )

        verified = (
            verified_department is not None
            and str(verified_department.get("departmentNumber")) == str(department_number)
        )

        return {
            "message": "Department updated successfully",
            "debug": {
                "updated_department_id": department_id,
                "updated_department_name": department_name,
                "updated_department_number": (
                    (verified_department or updated).get("departmentNumber")
                    or department_number
                ),
                "verified": verified,
            },
        }

    def _handle_delete_department(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        department_name = parsed.get("name")

        if not department_name:
            raise RuntimeError("Could not extract department name from prompt")

        existing_matches = self.client.search_departments(
            name=department_name,
            count=20,
        )
        exact_existing = next(
            (
                department
                for department in existing_matches
                if department.get("name") == department_name
            ),
            None,
        )

        if not exact_existing or not exact_existing.get("id"):
            raise RuntimeError(f'Department "{department_name}" was not found')

        department_id = int(exact_existing["id"])
        delete_result = self.client.delete(f"/department/{department_id}")

        verified_matches = self.client.search_departments(
            name=department_name,
            count=20,
        )
        verified_deleted = not any(
            department.get("id") == department_id for department in verified_matches
        )

        return {
            "message": "Department deleted successfully",
            "debug": {
                "deleted_department_id": department_id,
                "deleted_department_name": department_name,
                "delete_result": delete_result,
                "verified": verified_deleted,
            },
        }

    def _handle_create_employee(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        first_name = parsed.get("first_name")
        last_name = parsed.get("last_name")
        email = parsed.get("email")
        is_account_administrator = bool(parsed.get("is_account_administrator"))
        requested_user_type = "EXTENDED" if is_account_administrator else "NO_ACCESS"

        if not first_name or not last_name:
            raise RuntimeError("Could not extract employee name from prompt")

        default_department = self.client.get_default_department()
        if not default_department or not default_department.get("id"):
            raise RuntimeError("Could not find a default department to use for employee creation")
        department_id = int(default_department["id"])

        existing_matches = self.client.search_employees(
            first_name=first_name,
            last_name=last_name,
            email=email,
            count=20,
        )

        exact_existing = next(
            (
                employee
                for employee in existing_matches
                if employee.get("firstName") == first_name
                and employee.get("lastName") == last_name
                and (email is None or employee.get("email") == email)
            ),
            None,
        )

        employee_record = exact_existing
        reused_existing = employee_record is not None

        if employee_record is None:
            employee_record = self.client.create_employee(
                first_name=first_name,
                last_name=last_name,
                email=email,
                user_type=requested_user_type,
                department_id=department_id,
            )

        employee_id = employee_record.get("id")
        if not employee_id:
            raise RuntimeError("Employee was created but no employee id was returned")

        granted_template = None
        entitlements: List[Dict[str, Any]] = []

        if is_account_administrator:
            entitlements = self.client.list_employee_entitlements(int(employee_id), count=200)
            if not self._has_account_administrator_entitlement(entitlements):
                granted_template = "ALL_PRIVILEGES"
                self.client.grant_employee_entitlements_by_template(
                    employee_id=int(employee_id),
                    template=granted_template,
                )
                entitlements = self.client.list_employee_entitlements(
                    int(employee_id),
                    count=200,
                )

        verified_matches = self.client.search_employees(
            first_name=first_name,
            last_name=last_name,
            email=email,
            count=20,
        )
        verified_employee = next(
            (
                employee
                for employee in verified_matches
                if employee.get("id") == employee_id
                and employee.get("firstName") == first_name
                and employee.get("lastName") == last_name
            ),
            None,
        )

        verified = verified_employee is not None

        return {
            "message": "Employee created successfully" if not reused_existing else "Employee already exists",
            "debug": {
                "created_employee_id": employee_id,
                "created_employee_first_name": first_name,
                "created_employee_last_name": last_name,
                "created_employee_email": (verified_employee or employee_record).get("email") or email,
                "created_employee_user_type": (
                    (verified_employee or employee_record).get("userType") or requested_user_type
                ),
                "department_id": department_id,
                "is_account_administrator": is_account_administrator,
                "granted_entitlement_template": granted_template,
                "entitlement_count": len(entitlements),
                "has_account_administrator_entitlement": (
                    self._has_account_administrator_entitlement(entitlements)
                    if is_account_administrator
                    else False
                ),
                "verified": verified,
                "reused_existing": reused_existing,
            },
        }

    def _handle_create_project(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        if not parsed.get("name"):
            raise RuntimeError("Could not extract project name from prompt")

        parsed_customer_name = parsed.get("customer_name")
        customer_id = None

        if parsed_customer_name:
            customer_id = self._resolve_customer_id(parsed_customer_name)

        existing_matches = self.client.search_projects(
            name=parsed["name"],
            count=20,
        )

        exact_existing = next(
            (
                p
                for p in existing_matches
                if p.get("name") == parsed["name"]
                and (
                    customer_id is None
                    or (
                        p.get("customer")
                        and p["customer"].get("id") == customer_id
                    )
                )
            ),
            None,
        )

        if exact_existing:
            existing_customer = exact_existing.get("customer") or {}
            return {
                "message": "Project already exists",
                "debug": {
                    "created_project_id": exact_existing.get("id"),
                    "created_project_name": exact_existing.get("name"),
                    "project_manager_id": None,
                    "linked_customer_id": existing_customer.get("id"),
                    "linked_customer_name": existing_customer.get("name"),
                    "parsed_customer_name": parsed_customer_name,
                    "verified": True,
                    "reused_existing": True,
                },
            }

        default_employee = self.client.get_default_employee()
        if not default_employee or not default_employee.get("id"):
            raise RuntimeError("Could not find a default employee to use as project manager")

        project_manager_id = default_employee["id"]

        created = self.client.create_project(
            name=parsed["name"],
            project_manager_id=project_manager_id,
            customer_id=customer_id,
            start_date=None,
        )

        matches = self.client.search_projects(
            name=parsed["name"],
            count=20,
        )

        verified_match = next(
            (
                p
                for p in matches
                if p.get("id") == created.get("id")
                and p.get("name") == parsed["name"]
            ),
            None,
        )

        verified = verified_match is not None
        verified_customer = (verified_match or {}).get("customer") or {}

        return {
            "message": "Project created successfully",
            "debug": {
                "created_project_id": created.get("id"),
                "created_project_name": created.get("name"),
                "project_manager_id": project_manager_id,
                "linked_customer_id": verified_customer.get("id") or customer_id,
                "linked_customer_name": (
                    verified_customer.get("name") if verified_customer else parsed_customer_name
                ),
                "parsed_customer_name": parsed_customer_name,
                "verified": verified,
                "reused_existing": False,
            },
        }

    def _handle_update_project(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        project_name = parsed.get("name")
        customer_name = parsed.get("customer_name")

        if not project_name:
            raise RuntimeError("Could not extract project name from prompt")
        if not customer_name:
            raise RuntimeError("Could not extract updated project customer from prompt")

        project_matches = self.client.search_projects(name=project_name, count=20)
        exact_project = next(
            (project for project in project_matches if project.get("name") == project_name),
            None,
        )

        if not exact_project or not exact_project.get("id"):
            raise RuntimeError(f'Project "{project_name}" was not found')

        project_id = int(exact_project["id"])
        customer_id = self._resolve_customer_id(customer_name)

        updated = self.client.update_project(
            project_id=project_id,
            payload={"customer": {"id": customer_id}},
        )

        verified_matches = self.client.search_projects(name=project_name, count=20)
        verified_project = next(
            (
                project
                for project in verified_matches
                if project.get("id") == project_id
                and project.get("name") == project_name
            ),
            None,
        )

        verified_customer = (verified_project or {}).get("customer") or {}
        verified = verified_project is not None and verified_customer.get("id") == customer_id

        return {
            "message": "Project updated successfully",
            "debug": {
                "updated_project_id": project_id,
                "updated_project_name": project_name,
                "linked_customer_id": verified_customer.get("id") or customer_id,
                "linked_customer_name": verified_customer.get("name") or customer_name,
                "verified": verified,
                "beta_endpoint": True,
            },
        }

    def _handle_delete_project(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        project_name = parsed.get("name")

        if not project_name:
            raise RuntimeError("Could not extract project name from prompt")

        existing_matches = self.client.search_projects(name=project_name, count=20)
        exact_existing = next(
            (project for project in existing_matches if project.get("name") == project_name),
            None,
        )

        if not exact_existing or not exact_existing.get("id"):
            raise RuntimeError(f'Project "{project_name}" was not found')

        project_id = int(exact_existing["id"])
        delete_result = self.client.delete(f"/project/{project_id}")

        verified_matches = self.client.search_projects(name=project_name, count=20)
        still_exists = any(
            project.get("id") == project_id and project.get("name") == project_name
            for project in verified_matches
        )

        return {
            "message": "Project deleted successfully",
            "debug": {
                "deleted_project_id": project_id,
                "deleted_project_name": project_name,
                "delete_result": delete_result,
                "verified": not still_exists,
                "beta_endpoint": True,
            },
        }

    def _handle_create_travel_expense(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        title = parsed.get("title")
        if not title:
            raise RuntimeError("Could not extract travel expense title from prompt")

        default_employee = self.client.get_default_employee()
        if not default_employee or not default_employee.get("id"):
            raise RuntimeError("Could not find a default employee to use for travel expense creation")

        employee_id = int(default_employee["id"])
        created = self.client.create_travel_expense(
            employee_id=employee_id,
            title=title,
        )

        verified_matches = self.client.search_travel_expenses(
            employee_id=employee_id,
            count=20,
        )
        verified_expense = next(
            (
                expense
                for expense in verified_matches
                if expense.get("id") == created.get("id")
                and expense.get("title") == title
            ),
            None,
        )

        verified = verified_expense is not None

        return {
            "message": "Travel expense created successfully",
            "debug": {
                "created_travel_expense_id": created.get("id"),
                "created_travel_expense_title": title,
                "employee_id": employee_id,
                "state": (verified_expense or created).get("state"),
                "attachment_context": parsed.get("attachment_context"),
                "verified": verified,
            },
        }

    def _handle_delete_travel_expense(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        title = parsed.get("title")
        if not title:
            raise RuntimeError("Could not extract travel expense title from prompt")

        default_employee = self.client.get_default_employee()
        if not default_employee or not default_employee.get("id"):
            raise RuntimeError("Could not find a default employee to use for travel expense deletion")

        employee_id = int(default_employee["id"])
        existing_matches = self.client.search_travel_expenses(
            employee_id=employee_id,
            count=50,
        )
        exact_existing = next(
            (
                expense
                for expense in existing_matches
                if expense.get("title") == title
            ),
            None,
        )

        if not exact_existing or not exact_existing.get("id"):
            raise RuntimeError(f'Travel expense "{title}" was not found')

        expense_id = int(exact_existing["id"])
        delete_result = self.client.delete(f"/travelExpense/{expense_id}")

        verified_matches = self.client.search_travel_expenses(
            employee_id=employee_id,
            count=50,
        )
        verified_deleted = not any(
            expense.get("id") == expense_id for expense in verified_matches
        )

        return {
            "message": "Travel expense deleted successfully",
            "debug": {
                "deleted_travel_expense_id": expense_id,
                "deleted_travel_expense_title": title,
                "employee_id": employee_id,
                "delete_result": delete_result,
                "verified": verified_deleted,
            },
        }

    def _handle_update_travel_expense(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        current_title = parsed.get("title")
        updated_title = parsed.get("updated_title")

        if not current_title:
            raise RuntimeError("Could not extract travel expense title from prompt")
        if not updated_title:
            raise RuntimeError("Could not extract updated travel expense title from prompt")

        default_employee = self.client.get_default_employee()
        if not default_employee or not default_employee.get("id"):
            raise RuntimeError("Could not find a default employee to use for travel expense update")

        employee_id = int(default_employee["id"])
        existing_matches = self.client.search_travel_expenses(
            employee_id=employee_id,
            count=50,
        )
        exact_existing = next(
            (
                expense
                for expense in existing_matches
                if expense.get("title") == current_title
            ),
            None,
        )

        if not exact_existing or not exact_existing.get("id"):
            raise RuntimeError(f'Travel expense "{current_title}" was not found')

        expense_id = int(exact_existing["id"])
        updated = self.client.update_travel_expense(
            travel_expense_id=expense_id,
            payload={"title": updated_title},
        )

        verified_matches = self.client.search_travel_expenses(
            employee_id=employee_id,
            count=50,
        )
        verified_expense = next(
            (
                expense
                for expense in verified_matches
                if expense.get("id") == expense_id
            ),
            None,
        )

        verified = (
            verified_expense is not None
            and verified_expense.get("title") == updated_title
        )

        return {
            "message": "Travel expense updated successfully",
            "debug": {
                "updated_travel_expense_id": expense_id,
                "previous_travel_expense_title": current_title,
                "updated_travel_expense_title": (
                    (verified_expense or updated).get("title") or updated_title
                ),
                "employee_id": employee_id,
                "verified": verified,
            },
        }

    def _handle_create_order(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        customer_name = parsed.get("customer_name")
        product_name = parsed.get("product_name")
        quantity = parsed.get("quantity")
        project_name = parsed.get("project_name")

        if not customer_name:
            raise RuntimeError("Could not extract customer name from prompt")
        if not product_name:
            raise RuntimeError("Could not extract product name from prompt")
        if quantity is None:
            raise RuntimeError("Could not extract quantity from prompt")

        customer_id = self._resolve_customer_id(customer_name)
        product_id = self._resolve_product_id(product_name)
        invoice_bank_account = self.client.ensure_invoice_bank_account_number()

        project_id = None
        if project_name:
            project_id = self._resolve_project_id(project_name)

        created_order = self.client.create_order(
            customer_id=customer_id,
            order_date=None,
            project_id=project_id,
        )

        order_id = created_order.get("id")
        if not order_id:
            raise RuntimeError("Order was created but no order id was returned")

        created_line = self.client.create_order_line(
            order_id=int(order_id),
            product_id=product_id,
            quantity=float(quantity),
            unit_price=None,
            description=None,
        )

        verified_lines = self.client.search_order_lines(order_id=int(order_id), count=50)

        verified_line = next(
            (line for line in verified_lines if line.get("id") == created_line.get("id")),
            None,
        )

        verified = verified_line is not None

        return {
            "message": "Order created successfully",
            "debug": {
                "created_order_id": created_order.get("id"),
                "created_order_date": created_order.get("orderDate"),
                "created_order_line_id": created_line.get("id"),
                "linked_customer_id": customer_id,
                "linked_customer_name": customer_name,
                "linked_product_id": product_id,
                "linked_product_name": product_name,
                "linked_project_id": project_id,
                "linked_project_name": project_name,
                "invoice_bank_account_id": invoice_bank_account.get("id"),
                "invoice_bank_account_number": invoice_bank_account.get("bankAccountNumber"),
                "quantity": quantity,
                "verified": verified,
                "reused_existing": False,
            },
        }

    def _handle_delete_order(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        customer_name = parsed.get("customer_name")
        product_name = parsed.get("product_name")

        if not customer_name:
            raise RuntimeError("Could not extract customer name from prompt")
        if not product_name:
            raise RuntimeError("Could not extract product name from prompt")

        customer_id = self._resolve_customer_id(customer_name)
        product_id = self._resolve_product_id(product_name)

        existing_orders = self.client.search_orders(customer_id=customer_id, count=50)
        exact_order = None

        for order in existing_orders:
            order_id = order.get("id")
            if not order_id:
                continue
            lines = self.client.search_order_lines(order_id=int(order_id), count=50)
            if any(
                (line.get("product") or {}).get("id") == product_id
                for line in lines
            ):
                exact_order = order
                break

        if not exact_order or not exact_order.get("id"):
            raise RuntimeError(
                f'Order for customer "{customer_name}" with product "{product_name}" was not found'
            )

        order_id = int(exact_order["id"])
        delete_result = self.client.delete(f"/order/{order_id}")

        verified_orders = self.client.search_orders(customer_id=customer_id, count=50)
        still_exists = False
        for order in verified_orders:
            current_order_id = order.get("id")
            if current_order_id != order_id:
                continue
            lines = self.client.search_order_lines(order_id=int(current_order_id), count=50)
            if any(
                (line.get("product") or {}).get("id") == product_id
                for line in lines
            ):
                still_exists = True
                break

        return {
            "message": "Order deleted successfully",
            "debug": {
                "deleted_order_id": order_id,
                "linked_customer_id": customer_id,
                "linked_customer_name": customer_name,
                "linked_product_id": product_id,
                "linked_product_name": product_name,
                "delete_result": delete_result,
                "verified": not still_exists,
            },
        }

    def _handle_create_invoice(self, parsed: Dict[str, Any]) -> Dict[str, Any]:
        customer_name = parsed.get("customer_name")
        product_name = parsed.get("product_name")
        quantity = parsed.get("quantity")
        project_name = parsed.get("project_name")

        if not customer_name:
            raise RuntimeError("Could not extract customer name from prompt")
        if not product_name:
            raise RuntimeError("Could not extract product name from prompt")
        if quantity is None:
            raise RuntimeError("Could not extract quantity from prompt")

        customer_id = self._resolve_customer_id(customer_name)
        product_id = self._resolve_product_id(product_name)
        invoice_bank_account = self.client.ensure_invoice_bank_account_number()

        project_id = None
        if project_name:
            project_id = self._resolve_project_id(project_name)

        created_order = self.client.create_order(
            customer_id=customer_id,
            order_date=None,
            project_id=project_id,
        )

        order_id = created_order.get("id")
        if not order_id:
            raise RuntimeError("Order was created but no order id was returned")

        created_line = self.client.create_order_line(
            order_id=int(order_id),
            product_id=product_id,
            quantity=float(quantity),
            unit_price=None,
            description=None,
        )

        try:
            created_invoice = self.client.create_invoice(
                customer_id=customer_id,
                order_id=int(order_id),
                invoice_date=None,
                invoice_due_date=None,
                send_to_customer=False,
            )
        except RuntimeError as exc:
            message = str(exc)
            if self._is_invoice_bank_account_blocker(message):
                raise RuntimeError(
                    "Invoice creation is blocked because the Tripletex company has no registered bank account number"
                ) from exc
            raise

        invoice_id = created_invoice.get("id")
        if not invoice_id:
            raise RuntimeError("Invoice was created but no invoice id was returned")

        verified_invoices = self.client.search_invoices(
            customer_id=customer_id,
            count=50,
        )
        verified_invoice = next(
            (
                invoice
                for invoice in verified_invoices
                if invoice.get("id") == invoice_id
            ),
            None,
        )

        verified = verified_invoice is not None

        return {
            "message": "Invoice created successfully",
            "debug": {
                "created_invoice_id": invoice_id,
                "created_invoice_date": created_invoice.get("invoiceDate"),
                "created_invoice_due_date": created_invoice.get("invoiceDueDate"),
                "created_order_id": order_id,
                "created_order_line_id": created_line.get("id"),
                "linked_customer_id": customer_id,
                "linked_customer_name": customer_name,
                "linked_product_id": product_id,
                "linked_product_name": product_name,
                "linked_project_id": project_id,
                "linked_project_name": project_name,
                "invoice_bank_account_id": invoice_bank_account.get("id"),
                "invoice_bank_account_number": invoice_bank_account.get("bankAccountNumber"),
                "quantity": quantity,
                "verified": verified,
                "reused_existing": False,
            },
        }

    def _extract_customer_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", prompt)
        email = email_match.group(0) if email_match else None

        patterns = [
            r"create customer(?: named)?\s+(.+?)(?:,|\s+with email|\s+email|$)",
            r"register customer(?: named)?\s+(.+?)(?:,|\s+with email|\s+email|$)",
            r"opprett kunde(?: med navn)?\s+(.+?)(?:,|\s+med e-?post|\s+e-?post|$)",
            r"registrer kunde(?: med navn)?\s+(.+?)(?:,|\s+med e-?post|\s+e-?post|$)",
        ]

        name = None
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                name = match.group(1).strip(' ."\'')
                break

        return {
            "name": name,
            "email": email,
        }

    def _extract_customer_update_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", prompt)
        email = email_match.group(0) if email_match else None

        patterns = [
            r"update customer\s+(.+?)(?:\s+with email|\s+email)\s+[\w\.-]+@[\w\.-]+\.\w+",
            r"set email for customer\s+(.+?)\s+to\s+[\w\.-]+@[\w\.-]+\.\w+",
            r"oppdater kunde\s+(.+?)(?:\s+med e-?post|\s+e-?post)\s+[\w\.-]+@[\w\.-]+\.\w+",
            r"sett e-?post for kunde\s+(.+?)\s+til\s+[\w\.-]+@[\w\.-]+\.\w+",
        ]

        name = None
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                name = match.group(1).strip(' ."\'')
                break

        return {
            "name": name,
            "email": email,
        }

    def _extract_customer_delete_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        patterns = [
            r"delete customer\s+(.+)$",
            r"remove customer\s+(.+)$",
            r"slett kunde\s+(.+)$",
            r"fjern kunde\s+(.+)$",
        ]

        name = None
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                name = match.group(1).strip(' ."\'')
                break

        return {"name": name}

    def _extract_product_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        description = None

        description_patterns = [
            r"(?:with description|description)\s+(.+)$",
            r"(?:med beskrivelse|beskrivelse)\s+(.+)$",
        ]
        for pattern in description_patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                description = match.group(1).strip(' ."\'')
                break

        name_patterns = [
            r"create product(?: named)?\s+(.+?)(?:,|\s+with description|\s+description|$)",
            r"register product(?: named)?\s+(.+?)(?:,|\s+with description|\s+description|$)",
            r"opprett produkt(?: med navn)?\s+(.+?)(?:,|\s+med beskrivelse|\s+beskrivelse|$)",
            r"registrer produkt(?: med navn)?\s+(.+?)(?:,|\s+med beskrivelse|\s+beskrivelse|$)",
            r"create item(?: named)?\s+(.+?)(?:,|\s+with description|\s+description|$)",
        ]

        name = None
        for pattern in name_patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                name = match.group(1).strip(' ."\'')
                break

        return {
            "name": name,
            "description": description,
        }

    def _extract_product_update_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        description = None
        description_patterns = [
            r"(?:with description|description)\s+(.+)$",
            r"(?:med beskrivelse|beskrivelse)\s+(.+)$",
            r"(?:to description|til beskrivelse)\s+(.+)$",
        ]
        for pattern in description_patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                description = match.group(1).strip(' ."\'')
                break

        patterns = [
            r"update product\s+(.+?)(?:\s+with description|\s+description|\s+to description|$)",
            r"set description for product\s+(.+?)\s+to\s+.+$",
            r"oppdater produkt\s+(.+?)(?:\s+med beskrivelse|\s+beskrivelse|\s+til beskrivelse|$)",
            r"sett beskrivelse for produkt\s+(.+?)\s+til\s+.+$",
        ]

        name = None
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                name = match.group(1).strip(' ."\'')
                break

        return {
            "name": name,
            "description": description,
        }

    def _extract_product_delete_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        patterns = [
            r"delete product\s+(.+)$",
            r"remove product\s+(.+)$",
            r"slett produkt\s+(.+)$",
            r"fjern produkt\s+(.+)$",
        ]

        name = None
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                name = match.group(1).strip(' ."\'')
                break

        return {"name": name}

    def _extract_project_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        text = " ".join(prompt.strip().split())

        patterns = [
            r"opprett prosjekt(?: med navn)?\s+(?P<name>.+?)\s+for kunde\s+(?P<customer>.+)$",
            r"registrer prosjekt(?: med navn)?\s+(?P<name>.+?)\s+for kunde\s+(?P<customer>.+)$",
            r"create project(?: named)?\s+(?P<name>.+?)\s+for customer\s+(?P<customer>.+)$",
            r"register project(?: named)?\s+(?P<name>.+?)\s+for customer\s+(?P<customer>.+)$",
            r"opprett prosjekt(?: med navn)?\s+(?P<name>.+)$",
            r"registrer prosjekt(?: med navn)?\s+(?P<name>.+)$",
            r"create project(?: named)?\s+(?P<name>.+)$",
            r"register project(?: named)?\s+(?P<name>.+)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                name = match.group("name").strip(' ."\'')
                customer_name = match.groupdict().get("customer")
                if customer_name is not None:
                    customer_name = customer_name.strip(' ."\'')
                return {
                    "name": name,
                    "customer_name": customer_name,
                }

        return {
            "name": None,
            "customer_name": None,
        }

    def _extract_project_update_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        text = " ".join(prompt.strip().split())

        patterns = [
            r"oppdater prosjekt\s+(?P<name>.+?)\s+for kunde\s+(?P<customer>.+)$",
            r"sett kunde for prosjekt\s+(?P<name>.+?)\s+til\s+(?P<customer>.+)$",
            r"update project\s+(?P<name>.+?)\s+for customer\s+(?P<customer>.+)$",
            r"set customer for project\s+(?P<name>.+?)\s+to\s+(?P<customer>.+)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return {
                    "name": match.group("name").strip(' ."\''),
                    "customer_name": match.group("customer").strip(' ."\''),
                }

        return {
            "name": None,
            "customer_name": None,
        }

    def _extract_project_delete_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        patterns = [
            r"delete project\s+(.+)$",
            r"remove project\s+(.+)$",
            r"slett prosjekt\s+(.+)$",
            r"fjern prosjekt\s+(.+)$",
        ]

        name = None
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                name = match.group(1).strip(' ."\'')
                break

        return {"name": name}

    def _extract_travel_expense_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        patterns = [
            r"register travel expense(?: report)?\s+(.+)$",
            r"create travel expense(?: report)?\s+(.+)$",
            r"registrer reiseregning\s+(.+)$",
            r"opprett reiseregning\s+(.+)$",
        ]

        title = None
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                title = match.group(1).strip(' ."\'')
                break

        return {"title": title}

    def _extract_travel_expense_update_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        patterns = [
            r"update travel expense(?: report)?\s+(.+?)\s+to\s+(.+)$",
            r"set title for travel expense(?: report)?\s+(.+?)\s+to\s+(.+)$",
            r"oppdater reiseregning\s+(.+?)\s+til\s+(.+)$",
            r"sett tittel for reiseregning\s+(.+?)\s+til\s+(.+)$",
        ]

        title = None
        updated_title = None
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                title = match.group(1).strip(' ."\'')
                updated_title = match.group(2).strip(' ."\'')
                break

        return {
            "title": title,
            "updated_title": updated_title,
        }

    def _extract_travel_expense_delete_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        patterns = [
            r"delete travel expense(?: report)?\s+(.+)$",
            r"remove travel expense(?: report)?\s+(.+)$",
            r"slett reiseregning\s+(.+)$",
            r"fjern reiseregning\s+(.+)$",
        ]

        title = None
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                title = match.group(1).strip(' ."\'')
                break

        return {"title": title}

    def _extract_order_fields(self, prompt: str) -> Dict[str, Any]:
        text = " ".join(prompt.strip().split())

        quantity = 1.0
        quantity_match = re.search(
            r"(?:antall|qty|quantity)\s+(\d+(?:[.,]\d+)?)",
            text,
            flags=re.IGNORECASE,
        )
        if quantity_match:
            quantity = float(quantity_match.group(1).replace(",", "."))

        patterns = [
            r"opprett ordre\s+for kunde\s+(?P<customer>.+?)\s+med produkt\s+(?P<product>.+?)(?:\s+antall\s+(?P<quantity>\d+(?:[.,]\d+)?))?$",
            r"registrer ordre\s+for kunde\s+(?P<customer>.+?)\s+med produkt\s+(?P<product>.+?)(?:\s+antall\s+(?P<quantity>\d+(?:[.,]\d+)?))?$",
            r"create order\s+for customer\s+(?P<customer>.+?)\s+with product\s+(?P<product>.+?)(?:\s+quantity\s+(?P<quantity>\d+(?:[.,]\d+)?))?$",
            r"register order\s+for customer\s+(?P<customer>.+?)\s+with product\s+(?P<product>.+?)(?:\s+quantity\s+(?P<quantity>\d+(?:[.,]\d+)?))?$",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                parsed_quantity = match.groupdict().get("quantity")
                if parsed_quantity:
                    quantity = float(parsed_quantity.replace(",", "."))

                return {
                    "customer_name": match.group("customer").strip(' ."\''),
                    "product_name": match.group("product").strip(' ."\''),
                    "quantity": quantity,
                    "project_name": None,
                }

        return {
            "customer_name": None,
            "product_name": None,
            "quantity": quantity,
            "project_name": None,
        }

    def _extract_order_delete_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        text = " ".join(prompt.strip().split())

        patterns = [
            r"slett ordre\s+for kunde\s+(?P<customer>.+?)\s+med produkt\s+(?P<product>.+)$",
            r"fjern ordre\s+for kunde\s+(?P<customer>.+?)\s+med produkt\s+(?P<product>.+)$",
            r"delete order\s+for customer\s+(?P<customer>.+?)\s+with product\s+(?P<product>.+)$",
            r"remove order\s+for customer\s+(?P<customer>.+?)\s+with product\s+(?P<product>.+)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return {
                    "customer_name": match.group("customer").strip(' ."\''),
                    "product_name": match.group("product").strip(' ."\''),
                }

        return {
            "customer_name": None,
            "product_name": None,
        }

    def _extract_invoice_fields(self, prompt: str) -> Dict[str, Any]:
        text = " ".join(prompt.strip().split())

        quantity = 1.0
        quantity_match = re.search(
            r"(?:antall|qty|quantity)\s+(\d+(?:[.,]\d+)?)",
            text,
            flags=re.IGNORECASE,
        )
        if quantity_match:
            quantity = float(quantity_match.group(1).replace(",", "."))

        patterns = [
            r"opprett faktura\s+for kunde\s+(?P<customer>.+?)\s+med produkt\s+(?P<product>.+?)(?:\s+antall\s+(?P<quantity>\d+(?:[.,]\d+)?))?$",
            r"registrer faktura\s+for kunde\s+(?P<customer>.+?)\s+med produkt\s+(?P<product>.+?)(?:\s+antall\s+(?P<quantity>\d+(?:[.,]\d+)?))?$",
            r"create invoice\s+for customer\s+(?P<customer>.+?)\s+with product\s+(?P<product>.+?)(?:\s+quantity\s+(?P<quantity>\d+(?:[.,]\d+)?))?$",
            r"register invoice\s+for customer\s+(?P<customer>.+?)\s+with product\s+(?P<product>.+?)(?:\s+quantity\s+(?P<quantity>\d+(?:[.,]\d+)?))?$",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                parsed_quantity = match.groupdict().get("quantity")
                if parsed_quantity:
                    quantity = float(parsed_quantity.replace(",", "."))

                return {
                    "customer_name": match.group("customer").strip(' ."\''),
                    "product_name": match.group("product").strip(' ."\''),
                    "quantity": quantity,
                    "project_name": None,
                }

        return {
            "customer_name": None,
            "product_name": None,
            "quantity": quantity,
            "project_name": None,
        }

    def _extract_department_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        number = None

        number_patterns = [
            r"(?:department number|number)\s+([A-Za-z0-9\-_]+)",
            r"(?:avdelingsnummer|nummer)\s+([A-Za-z0-9\-_]+)",
        ]
        for pattern in number_patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                number = match.group(1).strip()
                break

        name_patterns = [
            r"create department(?: named)?\s+(.+?)(?:,|\s+with department number|\s+department number|\s+with number|\s+number|\s+with description|\s+description|$)",
            r"register department(?: named)?\s+(.+?)(?:,|\s+with department number|\s+department number|\s+with number|\s+number|\s+with description|\s+description|$)",
            r"opprett avdeling(?: med navn)?\s+(.+?)(?:,|\s+med avdelingsnummer|\s+avdelingsnummer|\s+med nummer|\s+nummer|\s+med beskrivelse|\s+beskrivelse|$)",
            r"registrer avdeling(?: med navn)?\s+(.+?)(?:,|\s+med avdelingsnummer|\s+avdelingsnummer|\s+med nummer|\s+nummer|\s+med beskrivelse|\s+beskrivelse|$)",
        ]

        name = None
        for pattern in name_patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                name = match.group(1).strip(' ."\'')
                break

        return {
            "name": name,
            "department_number": number,
        }

    def _extract_department_update_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        number = None
        number_patterns = [
            r"(?:department number|number)\s+([A-Za-z0-9\-_]+)",
            r"(?:avdelingsnummer|nummer)\s+([A-Za-z0-9\-_]+)",
            r"(?:to number|til nummer)\s+([A-Za-z0-9\-_]+)",
        ]
        for pattern in number_patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                number = match.group(1).strip()
                break

        patterns = [
            r"update department\s+(.+?)(?:\s+with department number|\s+department number|\s+with number|\s+number|\s+to number|$)",
            r"set department number for department\s+(.+?)\s+to\s+[A-Za-z0-9\-_]+",
            r"oppdater avdeling\s+(.+?)(?:\s+med avdelingsnummer|\s+avdelingsnummer|\s+med nummer|\s+nummer|\s+til nummer|$)",
            r"sett avdelingsnummer for avdeling\s+(.+?)\s+til\s+[A-Za-z0-9\-_]+",
        ]

        name = None
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                name = match.group(1).strip(' ."\'')
                break

        return {
            "name": name,
            "department_number": number,
        }

    def _extract_department_delete_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        patterns = [
            r"delete department\s+(.+?)(?:\s+with department number|\s+department number|\s+with number|\s+number|$)",
            r"remove department\s+(.+?)(?:\s+with department number|\s+department number|\s+with number|\s+number|$)",
            r"slett avdeling\s+(.+?)(?:\s+med avdelingsnummer|\s+avdelingsnummer|\s+med nummer|\s+nummer|$)",
            r"fjern avdeling\s+(.+?)(?:\s+med avdelingsnummer|\s+avdelingsnummer|\s+med nummer|\s+nummer|$)",
        ]

        name = None
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                name = match.group(1).strip(' ."\'')
                break

        return {"name": name}

    def _extract_employee_fields(self, prompt: str) -> Dict[str, Optional[str]]:
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", prompt)
        email = email_match.group(0) if email_match else None
        text = " ".join(prompt.strip().split())
        name_token = r"[A-Za-zÀ-ÖØ-öø-ÿÆØÅæøå\-]+"

        patterns = [
            rf"create employee(?: named)?\s+({name_token})\s+({name_token})(?:,|\s+with email|\s+email|$)",
            rf"register employee(?: named)?\s+({name_token})\s+({name_token})(?:,|\s+with email|\s+email|$)",
            rf"opprett ansatt(?: med navn)?\s+({name_token})\s+({name_token})(?:,|\s+med e-?post|\s+e-?post|$)",
            rf"registrer ansatt(?: med navn)?\s+({name_token})\s+({name_token})(?:,|\s+med e-?post|\s+e-?post|$)",
        ]

        first_name = None
        last_name = None

        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                first_name = match.group(1).strip()
                last_name = match.group(2).strip()
                break

        is_account_administrator = bool(
            re.search(
                r"\b(account administrator|administrator|kontoadministrator|kontoadministrator)\b",
                text,
                flags=re.IGNORECASE,
            )
        )

        return {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "is_account_administrator": is_account_administrator,
        }

    def _save_files(self, request: SolveRequest) -> List[SavedAttachment]:
        attachments_dir = Path("attachments")
        attachments_dir.mkdir(exist_ok=True)

        saved_files: List[SavedAttachment] = []

        for file_obj in request.files:
            filename = file_obj.filename or "unnamed_file"
            content_base64 = file_obj.content_base64 or ""

            if not content_base64:
                continue

            file_bytes = base64.b64decode(content_base64)
            file_path = attachments_dir / filename
            file_path.write_bytes(file_bytes)
            saved_files.append(
                SavedAttachment(
                    filename=filename,
                    path=str(file_path),
                    mime_type=file_obj.mime_type,
                )
            )

        return saved_files

    def _classify_prompt(self, prompt: str) -> str:
        p = self._normalize_prompt(prompt).lower()

        customer_words = ["customer", "kunde", "client"]
        product_words = ["product", "produkt", "item", "vare"]
        employee_words = ["employee", "ansatt", "medarbeider"]
        project_words = ["project", "prosjekt"]
        department_words = ["department", "avdeling"]
        order_words = ["order", "ordre"]
        invoice_words = ["invoice", "faktura"]
        travel_expense_words = ["travel expense", "expense report", "reiseregning"]
        payment_words = ["payment"]
        credit_note_words = ["credit note"]
        voucher_words = ["voucher"]
        ledger_words = ["general ledger", "ledger"]
        analysis_words = ["analyze", "identify", "increase", "increased", "costs", "expense account"]
        activity_words = ["activity"]
        create_words = ["create", "register", "opprett", "registrer"]
        update_words = ["update", "set", "oppdater", "sett"]
        delete_words = ["delete", "remove", "slett", "fjern"]

        if (
            self._contains_any_term(p, ledger_words)
            and self._contains_any_term(p, analysis_words)
            and (
                self._contains_any_term(p, activity_words)
                or self._contains_any_term(p, project_words)
            )
        ):
            return "ledger_analysis_unsupported"
        if self._contains_any_term(p, payment_words) and self._contains_any_term(
            p, create_words + delete_words + update_words
        ):
            return "payment_unsupported"
        if self._contains_any_term(p, credit_note_words) and self._contains_any_term(
            p, create_words + delete_words + update_words
        ):
            return "credit_note_unsupported"
        if self._contains_any_term(p, voucher_words) and self._contains_any_term(
            p, create_words + delete_words + update_words
        ):
            return "voucher_unsupported"
        if self._contains_any_term(p, employee_words) and self._contains_any_term(p, update_words):
            return "employee_update"
        if self._contains_any_term(p, employee_words) and self._contains_any_term(p, delete_words):
            return "employee_delete"
        if self._contains_any_term(p, invoice_words) and self._contains_any_term(p, update_words):
            return "invoice_update"
        if self._contains_any_term(p, order_words) and self._contains_any_term(p, update_words):
            return "order_update"
        if self._contains_any_term(p, project_words) and self._contains_any_term(p, create_words):
            return "project_create"
        if self._contains_any_term(p, project_words) and self._contains_any_term(p, update_words):
            return "project_update"
        if self._contains_any_term(p, project_words) and self._contains_any_term(p, delete_words):
            return "project_delete"
        if self._contains_any_term(p, travel_expense_words) and self._contains_any_term(p, create_words):
            return "travel_expense_create"
        if self._contains_any_term(p, travel_expense_words) and self._contains_any_term(p, update_words):
            return "travel_expense_update"
        if self._contains_any_term(p, travel_expense_words) and self._contains_any_term(p, delete_words):
            return "travel_expense_delete"
        if self._contains_any_term(p, invoice_words) and self._contains_any_term(p, delete_words):
            return "invoice_delete"
        if self._contains_any_term(p, invoice_words) and self._contains_any_term(p, create_words):
            return "invoice_create"
        if self._contains_any_term(p, order_words) and self._contains_any_term(p, create_words):
            return "order_create"
        if self._contains_any_term(p, order_words) and self._contains_any_term(p, delete_words):
            return "order_delete"
        if self._contains_any_term(p, customer_words) and self._contains_any_term(p, update_words):
            return "customer_update"
        if self._contains_any_term(p, customer_words) and self._contains_any_term(p, delete_words):
            return "customer_delete"
        if self._contains_any_term(p, department_words) and self._contains_any_term(p, update_words):
            return "department_update"
        if self._contains_any_term(p, department_words) and self._contains_any_term(p, delete_words):
            return "department_delete"
        if self._contains_any_term(p, product_words) and self._contains_any_term(p, update_words):
            return "product_update"
        if self._contains_any_term(p, product_words) and self._contains_any_term(p, delete_words):
            return "product_delete"
        if self._contains_any_term(p, department_words) and self._contains_any_term(p, create_words):
            return "department_create"
        if self._contains_any_term(p, product_words) and self._contains_any_term(p, create_words):
            return "product_create"
        if self._contains_any_term(p, employee_words) and self._contains_any_term(p, create_words):
            return "employee_create"
        if self._contains_any_term(p, customer_words) and self._contains_any_term(p, create_words):
            return "customer_create"

        return "unknown"
