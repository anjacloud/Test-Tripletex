import json
import subprocess
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlencode

import requests


class TripletexClient:
    DEFAULT_SANDBOX_INVOICE_BANK_ACCOUNT_NUMBER = "86011117947"

    def __init__(self, base_url: str, session_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = ("0", session_token)
        self.timeout = 30

    def _handle_response(self, response: requests.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except Exception:
            if response.ok:
                return {}
            response.raise_for_status()
            raise RuntimeError("Response was not valid JSON")

        if not response.ok:
            raise RuntimeError(self._format_error(response.status_code, data))

        return data

    def _format_error(self, status_code: int, data: dict[str, Any]) -> str:
        message = data.get("message", "Unknown Tripletex error")
        developer_message = data.get("developerMessage", "")
        validation_messages = data.get("validationMessages", [])
        request_id = data.get("requestId", "")

        return (
            f"HTTP {status_code}: {message} | "
            f"developerMessage={developer_message} | "
            f"validationMessages={validation_messages} | "
            f"requestId={request_id}"
        )

    def _should_retry_with_curl(self, exc: Exception) -> bool:
        message = str(exc).lower()
        dns_markers = [
            "name resolution",
            "failed to resolve",
            "temporary failure in name resolution",
            "nodename nor servname provided",
            "name or service not known",
        ]
        return any(marker in message for marker in dns_markers)

    def _handle_status_and_body(
        self,
        status_code: int,
        body: str,
    ) -> dict[str, Any]:
        if not body.strip():
            if 200 <= status_code < 300:
                return {}
            raise RuntimeError(f"HTTP {status_code}: Empty response body")

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            if 200 <= status_code < 300:
                return {}
            raise RuntimeError(f"HTTP {status_code}: Response was not valid JSON") from exc

        if not 200 <= status_code < 300:
            raise RuntimeError(self._format_error(status_code, data))

        return data

    def _curl_request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        query = f"?{urlencode(params, doseq=True)}" if params else ""
        url = f"{self.base_url}{path}{query}"
        command = [
            "curl",
            "-sS",
            "-X",
            method,
            "-u",
            f"{self.auth[0]}:{self.auth[1]}",
            "--max-time",
            str(self.timeout),
            "-H",
            "Accept: application/json",
            "-w",
            "\n__TRIPLETEX_HTTP_STATUS__:%{http_code}",
        ]
        if payload is not None:
            command.extend(
                [
                    "-H",
                    "Content-Type: application/json",
                    "--data",
                    json.dumps(payload),
                ]
            )
        command.append(url)

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"curl fallback failed for {method} {path}: {result.stderr.strip() or result.stdout.strip()}"
            )

        marker = "\n__TRIPLETEX_HTTP_STATUS__:"
        if marker not in result.stdout:
            raise RuntimeError(f"curl fallback failed for {method} {path}: missing status marker")

        body, status_text = result.stdout.rsplit(marker, 1)
        status_code = int(status_text.strip())
        return status_code, self._handle_status_and_body(status_code, body)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, Any]]:
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(
                method,
                url,
                auth=self.auth,
                params=params,
                json=payload,
                timeout=self.timeout,
            )
        except requests.exceptions.RequestException as exc:
            if self._should_retry_with_curl(exc):
                return self._curl_request(method, path, payload=payload, params=params)
            raise

        return response.status_code, self._handle_response(response)

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        _, data = self._request("GET", path, params=params)
        return data

    def post(
        self,
        path: str,
        payload: dict[str, Any],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _, data = self._request("POST", path, payload=payload, params=params)
        return data

    def put(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _, data = self._request("PUT", path, payload=payload, params=params)
        return data

    def delete(self, path: str) -> dict[str, Any]:
        status_code, data = self._request("DELETE", path)
        if status_code in (200, 204):
            return {"status": "deleted"}
        return data

    def list_employees(self) -> list[dict[str, Any]]:
        data = self.get(
            "/employee",
            params={"fields": "id,firstName,lastName,email", "count": 100},
        )
        return data.get("values", [])

    def create_customer(self, name: str, email: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "isCustomer": True,
        }
        if email:
            payload["email"] = email

        data = self.post("/customer", payload)
        return data.get("value", {})

    def update_customer(
        self,
        customer_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        data = self.put(f"/customer/{customer_id}", payload)
        return data.get("value", {})

    def search_customers(self, name: str, count: int = 10) -> list[dict[str, Any]]:
        data = self.get(
            "/customer",
            params={
                "name": name,
                "fields": "id,name,email,isCustomer",
                "count": count,
            },
        )
        return data.get("values", [])

    def list_products(self, count: int = 10, fields: str = "*") -> list[dict[str, Any]]:
        data = self.get(
            "/product",
            params={
                "count": count,
                "fields": fields,
            },
        )
        return data.get("values", [])

    def create_product_raw(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = self.post("/product", payload)
        return data.get("value", {})

    def update_product(
        self,
        product_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        data = self.put(f"/product/{product_id}", payload)
        return data.get("value", {})

    def create_product(
        self,
        name: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
        }
        if description:
            payload["description"] = description

        data = self.post("/product", payload)
        return data.get("value", {})

    def search_products(self, name: str, count: int = 10) -> list[dict[str, Any]]:
        data = self.get(
            "/product",
            params={
                "name": name,
                "fields": "id,name,description,isInactive",
                "count": count,
            },
        )
        return data.get("values", [])

    def create_employee(
        self,
        first_name: str,
        last_name: str,
        email: str | None = None,
        user_type: str | None = None,
        department_id: int | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "firstName": first_name,
            "lastName": last_name,
        }
        if email:
            payload["email"] = email
        if user_type:
            payload["userType"] = user_type
        if department_id is not None:
            payload["department"] = {"id": department_id}

        data = self.post("/employee", payload)
        return data.get("value", {})

    def search_employees(
        self,
        first_name: str | None = None,
        last_name: str | None = None,
        email: str | None = None,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "fields": "id,firstName,lastName,email,userType",
            "count": count,
        }
        if first_name:
            params["firstName"] = first_name
        if last_name:
            params["lastName"] = last_name
        if email:
            params["email"] = email

        data = self.get("/employee", params=params)
        return data.get("values", [])

    def list_employee_entitlements(
        self,
        employee_id: int,
        count: int = 200,
    ) -> list[dict[str, Any]]:
        data = self.get(
            "/employee/entitlement",
            params={
                "employeeId": employee_id,
                "count": count,
                "fields": "id,name,entitlementId,employee(id)",
            },
        )
        return data.get("values", [])

    def grant_employee_entitlements_by_template(
        self,
        employee_id: int,
        template: str,
    ) -> None:
        self.put(
            "/employee/entitlement/:grantEntitlementsByTemplate",
            params={
                "employeeId": employee_id,
                "template": template,
            },
        )

    def get_default_employee(self) -> dict[str, Any] | None:
        employees = self.list_employees()
        if not employees:
            return None
        return employees[0]

    def create_department(
        self,
        name: str,
        department_number: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "isInactive": False,
        }
        if department_number:
            payload["departmentNumber"] = department_number

        data = self.post("/department", payload)
        return data.get("value", {})

    def update_department(
        self,
        department_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        data = self.put(f"/department/{department_id}", payload)
        return data.get("value", {})

    def search_departments(
        self,
        name: str | None = None,
        department_number: str | None = None,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "fields": "id,name,departmentNumber,isInactive",
            "count": count,
        }
        if name:
            params["name"] = name
        if department_number:
            params["departmentNumber"] = department_number

        data = self.get("/department", params=params)
        return data.get("values", [])

    def get_default_department(self) -> dict[str, Any] | None:
        departments = self.search_departments(count=20)
        active_department = next(
            (department for department in departments if not department.get("isInactive")),
            None,
        )
        return active_department

    def create_project(
        self,
        name: str,
        project_manager_id: int,
        customer_id: int | None = None,
        start_date: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": name,
            "projectManager": {"id": project_manager_id},
            "startDate": start_date or date.today().isoformat(),
        }

        if customer_id is not None:
            payload["customer"] = {"id": customer_id}

        data = self.post("/project", payload)
        return data.get("value", {})

    def update_project(
        self,
        project_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        data = self.put(f"/project/{project_id}", payload)
        return data.get("value", {})

    def search_projects(
        self,
        name: str | None = None,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "fields": "id,name,customer(id,name),isClosed",
            "count": count,
        }

        if name:
            params["name"] = name

        data = self.get("/project", params=params)
        return data.get("values", [])

    def create_order(
        self,
        customer_id: int,
        order_date: str | None = None,
        project_id: int | None = None,
    ) -> dict[str, Any]:
        order_day = order_date or date.today().isoformat()
        payload: dict[str, Any] = {
            "customer": {"id": customer_id},
            "orderDate": order_day,
            "deliveryDate": order_day,
        }

        if project_id is not None:
            payload["project"] = {"id": project_id}

        data = self.post("/order", payload)
        return data.get("value", {})

    def search_orders(
        self,
        customer_id: int | None = None,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "fields": "id,orderDate,customer(id,name),project(id,name)",
            "count": count,
        }

        if customer_id is not None:
            params["customerId"] = customer_id

        data = self.get("/order", params=params)
        return data.get("values", [])

    def create_order_line(
        self,
        order_id: int,
        product_id: int,
        quantity: float,
        unit_price: float | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "order": {"id": order_id},
            "product": {"id": product_id},
            "count": quantity,
        }

        if unit_price is not None:
            payload["unitPriceExcludingVatCurrency"] = unit_price

        if description:
            payload["description"] = description

        data = self.post("/order/orderline", payload)
        return data.get("value", {})

    def search_order_lines(
        self,
        order_id: int,
        count: int = 50,
    ) -> list[dict[str, Any]]:
        data = self.get(
            "/order/orderline",
            params={
                "orderId": order_id,
                "fields": "id,count,description,product(id,name),order(id)",
                "count": count,
            },
        )
        return data.get("values", [])

    def create_invoice(
        self,
        customer_id: int,
        order_id: int,
        invoice_date: str | None = None,
        invoice_due_date: str | None = None,
        send_to_customer: bool = False,
    ) -> dict[str, Any]:
        invoice_day = invoice_date or date.today().isoformat()
        payload: dict[str, Any] = {
            "invoiceDate": invoice_day,
            "invoiceDueDate": invoice_due_date or invoice_day,
            "customer": {"id": customer_id},
            "orders": [{"id": order_id}],
        }

        data = self.post(
            "/invoice",
            payload,
            params={"sendToCustomer": str(send_to_customer).lower()},
        )
        return data.get("value", {})

    def search_invoices(
        self,
        customer_id: int | None = None,
        invoice_date_from: str | None = None,
        invoice_date_to: str | None = None,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        start_date = invoice_date_from or date.today().isoformat()
        end_date = invoice_date_to or (date.today() + timedelta(days=1)).isoformat()
        params: dict[str, Any] = {
            "invoiceDateFrom": start_date,
            "invoiceDateTo": end_date,
            "fields": "id,invoiceDate,invoiceDueDate,customer(id,name),orders(id)",
            "count": count,
        }
        if customer_id is not None:
            params["customerId"] = str(customer_id)

        data = self.get("/invoice", params=params)
        return data.get("values", [])

    def create_travel_expense(
        self,
        employee_id: int,
        title: str,
        departure_date: str | None = None,
        return_date: str | None = None,
        departure_from: str = "Oslo",
        destination: str = "Oslo",
        purpose: str = "Business trip",
    ) -> dict[str, Any]:
        travel_day = departure_date or date.today().isoformat()
        payload: dict[str, Any] = {
            "title": title,
            "employee": {"id": employee_id},
            "travelDetails": {
                "departureDate": travel_day,
                "returnDate": return_date or travel_day,
                "departureFrom": departure_from,
                "destination": destination,
                "purpose": purpose,
            },
        }

        data = self.post("/travelExpense", payload)
        return data.get("value", {})

    def search_travel_expenses(
        self,
        employee_id: int | None = None,
        departure_date_from: str | None = None,
        return_date_to: str | None = None,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        travel_day = departure_date_from or date.today().isoformat()
        params: dict[str, Any] = {
            "departureDateFrom": travel_day,
            "returnDateTo": return_date_to or (date.today() + timedelta(days=1)).isoformat(),
            "fields": "id,title,state,employee(id,firstName,lastName),number,date",
            "count": count,
        }
        if employee_id is not None:
            params["employeeId"] = str(employee_id)

        data = self.get("/travelExpense", params=params)
        return data.get("values", [])

    def update_travel_expense(
        self,
        travel_expense_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        data = self.put(f"/travelExpense/{travel_expense_id}", payload)
        return data.get("value", {})

    def search_ledger_accounts(
        self,
        is_bank_account: bool | None = None,
        is_invoice_account: bool | None = None,
        count: int = 20,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "count": count,
            "fields": "id,number,name,isBankAccount,isInvoiceAccount,bankAccountNumber",
        }
        if is_bank_account is not None:
            params["isBankAccount"] = str(is_bank_account).lower()
        if is_invoice_account is not None:
            params["isInvoiceAccount"] = str(is_invoice_account).lower()

        data = self.get("/ledger/account", params=params)
        return data.get("values", [])

    def get_invoice_bank_account(self) -> dict[str, Any] | None:
        accounts = self.search_ledger_accounts(
            is_bank_account=True,
            is_invoice_account=True,
            count=20,
        )
        return accounts[0] if accounts else None

    def update_ledger_account(
        self,
        account_id: int,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        data = self.put(f"/ledger/account/{account_id}", payload)
        return data.get("value", {})

    def ensure_invoice_bank_account_number(
        self,
        bank_account_number: str | None = None,
    ) -> dict[str, Any]:
        invoice_account = self.get_invoice_bank_account()
        if not invoice_account or not invoice_account.get("id"):
            raise RuntimeError("Could not find an invoice bank account to use for invoicing")

        if invoice_account.get("bankAccountNumber"):
            return invoice_account

        return self.update_ledger_account(
            account_id=int(invoice_account["id"]),
            payload={
                "bankAccountNumber": (
                    bank_account_number or self.DEFAULT_SANDBOX_INVOICE_BANK_ACCOUNT_NUMBER
                )
            },
        )
