# Bank Agent Project

Accounting Agent offline để xử lý sao kê ACB/MSB/VCB, phân loại báo nợ/báo có, nhận diện nghiệp vụ kế toán, suy luận mã đối tượng và sinh file trung gian cho RPA nhập VACOM.

Phiên bản hiện tại dùng kiến trúc mức 2: rule + entity extraction + alias/fuzzy matching + ML offline fallback + accounting verifier. Không dùng LLM/API cloud.

## 1. Chạy Bằng Venv

```powershell
cd C:\Users\Admin\Desktop\test\bank_agent_project
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python bank_agent.py --input-dir .\input --output-dir .\output
```

Nếu PowerShell chặn activate:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 2. Output Cho RPA

File chạy tạm cho RPA: `output/rpa_input.xlsx`

- `BAO_NO_INPUT`: chỉ dòng báo nợ OK để RPA nhập luồng báo nợ ngân hàng.
- `BAO_CO_INPUT`: chỉ dòng báo có OK để RPA nhập luồng báo có ngân hàng.
- `EXCEPTION`: dòng lỗi, chưa chắc chắn, thiếu mã đối tượng, bảo hiểm, hoặc bị verifier chặn.
- `SUMMARY`: thống kê số dòng và tổng tiền.
- `RPA_TASKS`: mapping giữa dòng input và dòng trạng thái bền vững.

Hai sheet input đều có đúng 6 cột:

```text
Ngày CT | Mã ĐT | Lí do | TK nợ | TK có | Thành tiền
```

File tracking: `output/rpa_tracking.json`

Tracking có thêm:

- `entities`: đối tượng gợi ý, nội dung đã làm sạch, hóa đơn, MST, intent.
- `object_match_source`: `alias_match`, `entity_match`, `fuzzy_name`, `tax_code`.
- `ml_result`: kết quả ML nếu có model.
- `verification_result`: kiểm tra cuối trước khi xuất RPA.

File trạng thái bền vững: `output/rpa_summary.xlsx`

- Sheet `RPA_SUMMARY` lưu từng giao dịch theo `transaction_uid`, file/sheet/dòng gốc và trạng thái RPA.
- Trạng thái `hoàn thành` sẽ không được đưa lại vào `rpa_input.xlsx` ở các lần chạy sau.
- Trạng thái `chưa nhập` và `lỗi` được phép đưa vào `rpa_input.xlsx` để RPA chạy.
- Trạng thái `đang nhập` từ run cũ sẽ chuyển thành `cần kiểm tra` để tránh nhập trùng nếu RPA bị dừng giữa chừng.
- Nếu RPA chạy bằng Python, dùng `mark_rpa_started`, `mark_rpa_done`, `mark_rpa_error` trong `src.rpa_summary` để cập nhật summary ngay sau từng dòng.

## 3. Config Quan Trọng

- `config/own_company.yaml`: khai báo công ty mình để không bao giờ chọn nhầm mã ĐT như `LE PHAM`.
- `config/object_aliases.yaml`: alias thực tế trên sao kê, ví dụ `KBB`, `PETROLIMEX`, `VINH LONG`, `VSICO`.
- `config/default_rules.yaml`: rule nghiệp vụ kế toán.
- `config/ml.yaml`: đường dẫn model ML offline.

Khi gặp mã ĐT hay sai, ưu tiên bổ sung alias vào `object_aliases.yaml` trước. Đây là cách ổn định và dễ kiểm toán nhất.

## 4. Feedback Và Train ML Offline

Template feedback:

```text
data/training/reviewed_transactions.xlsx
```

Kế toán có thể điền các cột:

- `correct_use_case`
- `correct_account`
- `correct_object_code`
- `correct_object_name`
- `review_status`

Train model phân loại giao dịch:

```powershell
python -m src.ml.train_models --feedback data\training\reviewed_transactions.xlsx
```

Model sẽ lưu vào:

```text
models/transaction_classifier.joblib
```

Nếu chưa có model, chương trình vẫn chạy bình thường bằng rule + entity + alias + fuzzy.

## 5. Chạy Test

```powershell
python -m pytest --basetemp .pytest_tmp
```

## 6. File Input

- Sao kê ACB/MSB/VCB: `input/statements/`
- Danh mục phải thu: `input/DS mã đối tượng phải thu.xlsx`
- Danh mục phải trả: `input/DS mã đối tượng phải trả.xlsx`
- File quy luật: `input/quy_luat_da_bo_TNDN_o_TNCN.xlsx`

Nếu file quy luật Excel chưa đủ chuẩn, chương trình tự dùng `config/default_rules.yaml`.

## 7. Nguyên Tắc An Toàn

- Không chắc thì đưa vào `EXCEPTION`.
- Bảo hiểm luôn không xử lý tự động.
- Mã ĐT công ty mình bị chặn tuyệt đối.
- ML không ghi thẳng vào RPA output; mọi dòng phải qua accounting verifier.
