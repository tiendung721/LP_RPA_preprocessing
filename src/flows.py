from __future__ import annotations

from dataclasses import dataclass


FLOW_BAO_NO = "bao_no"
FLOW_BAO_CO = "bao_co"
FLOW_THU_TIEN_MAT = "thu_tien_mat"
FLOW_CHI_TIEN_MAT = "chi_tien_mat"

MONEY_OUT = "money_out"
MONEY_IN = "money_in"
MONEY_UNKNOWN = "unknown"

CASH_ACCOUNT = "1111"


@dataclass(frozen=True)
class FlowSpec:
    code: str
    input_sheet: str
    voucher_type: str
    execution_order: int


FLOW_SPECS: dict[str, FlowSpec] = {
    FLOW_BAO_NO: FlowSpec(FLOW_BAO_NO, "BAO_NO_INPUT", "Báo nợ ngân hàng", 1),
    FLOW_BAO_CO: FlowSpec(FLOW_BAO_CO, "BAO_CO_INPUT", "Báo có ngân hàng", 2),
    FLOW_THU_TIEN_MAT: FlowSpec(FLOW_THU_TIEN_MAT, "THU_TIEN_MAT_INPUT", "Phiếu thu tiền mặt", 3),
    FLOW_CHI_TIEN_MAT: FlowSpec(FLOW_CHI_TIEN_MAT, "CHI_TIEN_MAT_INPUT", "Phiếu chi tiền mặt", 4),
}

PAD_FLOW_ORDER = [FLOW_BAO_NO, FLOW_BAO_CO, FLOW_THU_TIEN_MAT, FLOW_CHI_TIEN_MAT]


def flow_sheet(flow: str) -> str:
    return FLOW_SPECS.get(flow, FlowSpec(flow, flow.upper(), flow, 99)).input_sheet


def flow_voucher_type(flow: str) -> str:
    return FLOW_SPECS.get(flow, FlowSpec(flow, flow, flow, 99)).voucher_type


def flow_execution_order(flow: str) -> int:
    return FLOW_SPECS.get(flow, FlowSpec(flow, flow, flow, 99)).execution_order

