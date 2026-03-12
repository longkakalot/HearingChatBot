\# HearingChatBot\_Githu



HearingChatBot là project nghiên cứu hỗ trợ phân tích dữ liệu thính học từ file PDF scan.



\## Current status

\- Phase 1: Tympanometry pipeline đã chạy ổn

\- Đã refactor sang `modules/tymp` và `modules/dataset`

\- Đang chuẩn bị sang Phase 2: Acoustic Reflex



\## Main structure

\- `app.py`: Streamlit entry

\- `modules/`: domain modules

\- `outputs/`: runtime outputs (không đưa lên GitHub)



\## Run locally

```bash

pip install -r requirements.txt

streamlit run app.py

