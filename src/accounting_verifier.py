from __future__ import annotations

from .entity_extractor import OwnCompanyConfig
from .models import ProcessedTransaction, Rule, VerificationResult


class AccountingVerifier:
    def __init__(self, bank_accounts: dict[str, str], own_company: OwnCompanyConfig):
        self.bank_accounts = bank_accounts
        self.own_company = own_company

    def verify(self, item: ProcessedTransaction, rule: Rule | None = None) -> VerificationResult:
        errors: list[str] = []
        bank_account = self.bank_accounts.get(item.bank, "")
        checks = {
            "bank_account": bank_account,
            "not_own_company": True,
            "flow_accounts_valid": True,
        }

        if item.object_code and self.own_company.is_own_code(item.object_code):
            checks["not_own_company"] = False
            errors.append("Mã đối tượng là công ty mình")
        if item.object_name and self.own_company.is_own_name(item.object_name):
            checks["not_own_company"] = False
            errors.append("Tên đối tượng là công ty mình")

        if item.flow == "bao_no" and bank_account and item.credit_account != bank_account:
            checks["flow_accounts_valid"] = False
            errors.append("Báo nợ phải có TK có là tài khoản ngân hàng")
        if item.flow == "bao_co" and bank_account and item.debit_account != bank_account:
            checks["flow_accounts_valid"] = False
            errors.append("Báo có phải có TK nợ là tài khoản ngân hàng")

        if rule and not rule.auto_process:
            errors.append(rule.error_note or "Rule không xử lý tự động")

        if rule and rule.requires_object:
            if not item.object_code or item.object_code == "ERROR":
                errors.append("Nghiệp vụ bắt buộc mã đối tượng nhưng chưa có mã hợp lệ")
            if item.confidence and item.confidence < 0.8:
                errors.append("Độ tin cậy mã đối tượng thấp")

        status = "ERROR" if errors else "OK"
        return VerificationResult(status=status, error_note="; ".join(dict.fromkeys(errors)), checks=checks)
