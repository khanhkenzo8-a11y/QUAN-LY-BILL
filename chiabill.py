!pip install streamlit google-generativeai pillow pyngrok -q
%%writefile app.py
import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
from datetime import datetime
import urllib.parse

st.set_page_config(page_title="Chia Bill Ăn Trưa Pro", page_icon="🍱", layout="wide")
st.title("🍱 Hệ Thống Chia Bill & Quản Lý Dư Nợ Tự Động")

if "GEMINI_API_KEY" in st.secrets:
    API_KEY = st.secrets["GEMINI_API_KEY"]
else:
    API_KEY = "AIzaSyABOThHacYN3tlr3fWM15PW2gScn-cUTFo"

genai.configure(api_key=API_KEY)

if "users" not in st.session_state:
    fixed_users = ["Tiến Anh", "Khánh", "Đức", "Đức Nhỏ", "Dũng", "Đạt"]
    st.session_state.users = [{"name": name, "balance": 0} for name in fixed_users]

BANK_INFO = {
    "bank": "Techcombank",
    "account_num": "7710 3939 39",
    "account_name": "NGO DUY KHANH"
}

col1, col2, col3 = st.columns([1.2, 1.8, 1.5])

with col1:
    st.header("👥 Thành Viên & Dư Nợ")
    st.write("### Bảng theo dõi nợ lũy kế:")
    for idx, u in enumerate(st.session_state.users):
        bal = u['balance']
        color = "green" if bal >= 0 else "red"
        c_name, c_btn = st.columns([2, 1.2])
        with c_name:
            st.markdown(f"**{u['name']}**: <span style='color:{color}; font-weight:bold;'>{bal:,} đ</span>", unsafe_allow_html=True)
        with c_btn:
            if bal < 0:
                if st.button(f"💵 Đã Trả", key=f"pay_{idx}"):
                    u['balance'] = 0
                    st.success(f"Đã xóa nợ cho {u['name']}!")
                    st.rerun()
    st.write("---")
    new_user = st.text_input("Thêm người mới (nếu có):")
    if st.button("Thêm thành viên"):
        if new_user.strip() and not any(u['name'] == new_user.strip() for u in st.session_state.users):
            st.session_state.users.append({"name": new_user.strip(), "balance": 0})
            st.rerun()
    if st.button("Reset tất cả dư nợ về 0", type="primary"):
        for u in st.session_state.users:
            u['balance'] = 0
        st.rerun()

with col2:
    st.header("📸 Quét Bill & Chọn Người Ăn")
    user_names = [u['name'] for u in st.session_state.users]
    payer = st.selectbox("🙋‍♂️ Ai là người ứng tiền trả quán?", options=user_names)
    st.write("🎯 **Tích chọn những người tham gia ăn bữa này:**")
    selected_diners = []
    grid_cols = st.columns(3)
    for idx, name in enumerate(user_names):
        with grid_cols[idx % 3]:
            if st.checkbox(name, value=True, key=f"diner_{name}"):
                selected_diners.append(name)
    uploaded_file = st.file_uploader("Chọn ảnh chụp màn hình hóa đơn...", type=["jpg", "jpeg", "png"])

    if uploaded_file is not None:
        image = Image.open(uploaded_file)
        st.image(image, caption="Ảnh hóa đơn đã tải", use_container_width=True)
        if st.button("⚡ CHẠY AI CHIA TIỀN TỰ ĐỘNG", type="secondary"):
            if not payer: st.error("Vui lòng chọn người trả tiền!")
            elif len(selected_diners) == 0: st.error("Vui lòng tích chọn ít nhất 1 người!")
            else:
                with st.spinner("Gemini AI đang bóc tách hóa đơn..."):
                    diners_str = ", ".join(selected_diners)
                    prompt = f"""Bạn là trợ lý kế toán. Hãy đọc ảnh hóa đơn này và trích xuất dữ liệu thành JSON thuần. Dựa trên danh sách người ăn: [{diners_str}]. Trả về JSON đúng cấu trúc không bọc ký tự markdown: {{"order_id": "Mã đơn hàng", "items": [{{"name": "Tên món", "original_price": 50000, "assigned_to": ["Tên người ăn"]}}], "total_food_temporary": 100000, "delivery_fee": 15000, "discounts": [{{"description": "Giảm giá", "amount": 10000}}], "final_total": 105000}}"""
                    try:
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        response = model.generate_content([prompt, image])
                        res_text = response.text.strip().replace("```json", "").replace("```", "")
                        bill_data = json.loads(res_text)
                        
                        total_food_temp = bill_data['total_food_temporary']
                        food_discount = sum(d['amount'] for d in bill_data['discounts'] if 'ship' not in d['description'].lower())
                        ship_discount = sum(d['amount'] for d in bill_data['discounts'] if 'ship' in d['description'].lower())
                        net_ship = bill_data['delivery_fee'] - ship_discount
                        discount_ratio = food_discount / total_food_temp if total_food_temp > 0 else 0
                        ship_per_person = net_ship / len(selected_diners) if selected_diners else 0
                        
                        current_shares = {name: 0 for name in user_names}
                        for item in bill_data['items']:
                            discounted_price = item['original_price'] * (1 - discount_ratio)
                            valid_sharers = [u for u in item['assigned_to'] if u in selected_diners]
                            if not valid_sharers: valid_sharers = selected_diners
                            price_per_sharer = discounted_price / len(valid_sharers)
                            for u in valid_sharers: current_shares[u] += price_per_sharer
                        for u in selected_diners: current_shares[u] += ship_per_person
                        for name in current_shares: current_shares[name] = int(round(current_shares[name]))

                        st.session_state.last_bill = {
                            "payer": payer, "order_id": bill_data.get('order_id', 'DH123'),
                            "final_total": bill_data['final_total'], "shares": current_shares, "date": datetime.now().strftime("%d%m")
                        }
                        final_total_bill = bill_data['final_total']
                        for u in st.session_state.users:
                            name = u['name']
                            if name == payer: u['balance'] += (final_total_bill - current_shares.get(name, 0))
                            else: u['balance'] -= current_shares.get(name, 0)
                            u['balance'] = int(round(u['balance']))
                        st.rerun()
                    except Exception as e: st.error(f"Lỗi: {e}")

with col3:
    st.header("💳 Thanh Toán")
    if "last_bill" in st.session_state:
        bill = st.session_state.last_bill
        st.success(f"🎉 Tổng bill: **{bill['final_total']:,} đ**")
        st.write(f"🆔 Đơn: {bill['order_id']} | 👤 Người trả: {bill['payer']}")
        summary_shares = []
        for name, amount in bill['shares'].items():
            if amount > 0 and name != bill['payer']:
                summary_shares.append({"Thành Viên": name, "Số Tiền": f"{amount:,} đ"})
        if summary_shares:
            st.table(summary_shares)
            selected_nợ = st.selectbox("Chọn người hiển thị QR:", options=[s["Thành Viên"] for s in summary_shares])
            if selected_nợ:
                amount = bill['shares'][selected_nợ]
                noidung_goc = f"{selected_nợ.upper()} - {bill['order_id']} - {bill['date']}"
                noidung_encoded = urllib.parse.quote(noidung_goc)
                qr_url = f"https://img.vietqr.io/image/{BANK_INFO['bank']}-{BANK_INFO['account_num']}-compact2.png?amount={amount}&addInfo={noidung_encoded}&accountName={BANK_INFO['account_name']}"
                st.write(f"📝 Nội dung CK: `{noidung_goc}`")
                st.image(qr_url, width=250)
    else: st.info("Chưa có đơn hàng nào được quét.")