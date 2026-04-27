"""Gathers code context from the codebase for error analysis.
In a real system this would grep source files; here we provide sample context."""

SAMPLE_CODE_CONTEXT = {
    "backend/services/order_service.py": {
        "lines": "138-150",
        "content": """class OrderService:
    def get_pending_orders(self, db_session):
        # Known issue: no timeout configured for this query
        query = "SELECT * FROM orders WHERE status='pending'"
        result = db_session.execute(query)  # line 142 - timeout occurs here
        return result.fetchall()

    def retry_with_backoff(self, fn, retries=3):
        for i in range(retries):
            try:
                return fn()
            except ConnectionError:
                time.sleep(2 ** i)
        raise ConnectionError("All retries exhausted")""",
    },
    "backend/services/checkout_service.py": {
        "lines": "82-95",
        "content": """class CheckoutService:
    def process_checkout(self, session, cart):
        # BUG: session can be None if auth middleware fails silently
        user_id = session.user_id  # line 87 - NullPointerException here
        order = Order(user_id=user_id, items=cart.items)
        total = self.calculate_total(order)

        if total > 0:
            payment = self.payment_service.charge(user_id, total)
            if payment.success:
                return self.finalize_order(order, payment)
        return CheckoutResult(success=False, error="Invalid total")""",
    },
    "backend/workers/data_processor.py": {
        "lines": "198-215",
        "content": """class DataProcessor:
    def process_batch(self, records):
        results = []
        # BUG: loading all records into memory without streaming
        for record in records:
            transformed = self.transform(record)  # line 203 - OOM happens here
            results.append(transformed)  # accumulates in memory
        return results

    def transform(self, record):
        # Heavy transformation that creates large intermediate objects
        enriched = self.enrich_with_external_data(record)
        validated = self.validate_schema(enriched)
        return validated""",
    },
    "backend/middleware/auth.py": {
        "lines": "50-65",
        "content": """class AuthMiddleware:
    def validate_token(self, token):
        if not token:
            raise AuthenticationError("No token provided")
        try:
            payload = jwt.decode(token, self.secret, algorithms=["HS256"])
            if payload['exp'] < time.time():  # line 56 - expired token
                raise AuthenticationError("Token expired")
            return payload
        except jwt.InvalidTokenError as e:
            raise AuthenticationError(f"Invalid token: {e}")

    def check_rate_limit(self, ip):
        count = self.rate_store.increment(ip)
        if count > self.max_requests:
            raise RateLimitError(f"Rate limit exceeded for {ip}")""",
    },
    "backend/services/payment_service.py": {
        "lines": "112-130",
        "content": """class PaymentService:
    def charge(self, customer_id, amount):
        try:
            response = self.client.post(
                f"{self.base_url}/v1/charges",
                json={"customer": customer_id, "amount": int(amount * 100)},
                timeout=30,  # line 118 - external API timeout
            )
            if response.status_code == 503:
                raise ExternalAPIError("Payment gateway unavailable")
            response.raise_for_status()
            return ChargeResult(success=True, charge_id=response.json()["id"])
        except httpx.TimeoutException:
            raise ExternalAPIError("Payment gateway timeout")""",
    },
}


def get_code_context(error_logs: list) -> str:
    """Build code context string from error logs by matching source file references."""
    context_parts = []
    matched_files = set()

    for log in error_logs:
        source = getattr(log, "source", None) or ""
        for file_path, ctx in SAMPLE_CODE_CONTEXT.items():
            if file_path in source and file_path not in matched_files:
                matched_files.add(file_path)
                context_parts.append(
                    f"--- {file_path} (lines {ctx['lines']}) ---\n{ctx['content']}"
                )

    # If no specific match, include the most likely context
    if not context_parts:
        for log in error_logs:
            msg = getattr(log, "message", str(log)).lower()
            if "timeout" in msg or "database" in msg or "connection" in msg:
                fp = "backend/services/order_service.py"
            elif "none" in msg or "null" in msg or "attribute" in msg:
                fp = "backend/services/checkout_service.py"
            elif "memory" in msg or "oom" in msg or "heap" in msg:
                fp = "backend/workers/data_processor.py"
            elif "auth" in msg or "token" in msg:
                fp = "backend/middleware/auth.py"
            elif "payment" in msg or "charge" in msg or "503" in msg:
                fp = "backend/services/payment_service.py"
            else:
                continue
            if fp not in matched_files:
                matched_files.add(fp)
                ctx = SAMPLE_CODE_CONTEXT[fp]
                context_parts.append(
                    f"--- {fp} (lines {ctx['lines']}) ---\n{ctx['content']}"
                )

    return "\n\n".join(context_parts) if context_parts else "No relevant code context found."
