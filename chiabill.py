import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
from datetime import datetime
import urllib.parse

# 1. CẤU HÌNH GIAO DIỆN WEB
st.set_page_config(page_title="Chia Bill Ăn Trưa Pro", page_icon="🍱", layout="wide")
st.title("🍱 Hệ Thống Chia Bill & Quản Lý Dư Nợ Tự Động")
st.write("Tải ảnh hóa đơn Grab/ShopeeFood, chọn người ăn, hệ thống tự chia tiền và tạo QR chuyển khoản!")

# 2. BẢO MẬT API KEY GEMINI
API_KEY = "AIzaSyAoDQi9wvUN_3Hx9E6V4wwjHE2auLAK47I"

genai.configure(api_key=API_KEY)

# 3. KHỞI TẠO DANH SÁCH THÀNH VIÊN CỐ ĐỊNH
if "users" not in st.session_state:
    fixed_users = ["Tiến Anh", "Khánh", "Đức", "Đức Nhỏ", "Dũng", "Đạt"]
    st.session_state.users = [{"name": name, "balance": 0} for name in fixed_users]

# Cấu hình tài khoản ngân hàng nhận tiền
BANK_INFO = {
    "bank": "Techcombank",
    "account_num": "7710 3939 39",
    "account_name": "NGO DUY KHANH"
}

# --- BỐ CỤC GIAO DIỆN: 3 CỘT ---
col1, col2, col3 = st.columns([1.2, 1.8, 1.5])

# =========================================================================
# CỘT 1: QUẢN LÝ THÀNH VIÊN & THANH TOÁN DƯ NỢ
# =========================================================================
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

# =========================================================================
# CỘT 2: TẢI BILL & TÍCH CHỌN NGƯỜI ĂN
# =========================================================================
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
            if not payer:
                st.error("Vui lòng chọn người trả tiền!")
            elif len(selected_diners) == 0:
                st.error("Vui lòng tích chọn ít nhất 1 người tham gia ăn!")
            else:
                with st.spinner("Gemini AI đang bóc tách hóa đơn và chia tiền..."):
                    diners_str = ", ".join(selected_diners)
                    
                    prompt = f"""
                    Bạn là một trợ lý kế toán chuyên nghiệp. Hãy đọc ảnh hóa đơn đồ ăn được cung cấp và trích xuất dữ liệu chính xác thành định dạng cấu trúc JSON.
                    Dựa trên danh sách người tham gia ăn hôm nay: [{diners_str}]. Hãy phân tích tên món ăn trong bill và phân bổ gán người ăn phù hợp nhất (nếu không rõ, hãy chia đều cho mọi người).
                    
                    BẮT BUỘC TRẢ VỀ cú pháp định dạng JSON thuần túy, tuyệt đối không bao bọc trong ký tự markdown như ```json hay chữ ```, không chứa khoảng trống thừa:
                    {{
                      "order_id": "Mã đơn hàng gồm các chữ số hoặc chữ cái viết liền",
                      "items": [
                        {{"name": "Tên món ăn cụ thể", "original_price": 50000, "assigned_to": ["Tên người ăn"]}}
                      ],
                      "total_food_temporary": 100000,
                      "delivery_fee": 15000,
                      "discounts": [
                        {{"description": "Mô tả voucher", "amount": 10000}}
                      ],
                      "final_total": 105000
                    }}
                    """
                    
                    try:
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        response = model.generate_content([prompt, image])
                        
                        # Làm sạch chuỗi JSON trả về
                        res_text = response.text.strip()
                        if res_text.startswith("```json"):
                            res_text = res_text[7:]
                        if res_text.endswith("```"):
                            res_text = res_text[:-3]
                        res_text = res_text.strip()
                        
                        bill_data = json.loads(res_text)
                        
                        # --- THUẬT TOÁN KẾ TOÁN CHIA TIỀN ---
                        total_food_temp = bill_data.get('total_food_temporary', 0)
                        final_total_bill = bill_data.get('final_total', 0)
                        delivery_fee = bill_data.get('delivery_fee', 0)
                        
                        food_discount = sum(d.get('amount', 0) for d in bill_data.get('discounts', []) if 'ship' not in d.get('description', '').lower())
                        ship_discount = sum(d.get('amount', 0) for d in bill_data.get('discounts', []) if 'ship' in d.get('description', '').lower())
                        net_ship = delivery_fee - ship_discount
                        
                        discount_ratio = food_discount / total_food_temp if total_food_temp > 0 else 0
                        ship_per_person = net_ship / len(selected_diners) if selected_diners else 0
                        
                        current_shares = {name: 0 for name in user_names}
                        for item in bill_data.get('items', []):
                            orig_price = item.get('original_price', 0)
                            discounted_price = orig_price * (1 - discount_ratio)
                            
                            valid_sharers = [u for u in item.get('assigned_to', []) if u in selected_diners]
                            if not valid_sharers: 
                                valid_sharers = selected_diners
                            
                            price_per_sharer = discounted_price / len(valid_sharers)
                            for u in valid_sharers:
                                current_shares[u] += price_per_sharer
                                
                        for u in selected_diners:
                            current_shares[u] += ship_per_person
                            
                        for name in current_shares:
                            current_shares[name] = int(round(current_shares[name]))

                        # Lưu thông tin đơn vào session
                        st.session_state.last_bill = {
                            "payer": payer,
                            "order_id": bill_data.get('order_id', 'DH' + datetime.now().strftime("%H%M")),
                            "final_total": final_total_bill,
                            "shares": current_shares,
                            "date": datetime.now().strftime("%d%m")
                        }
                        
                        # --- CẬP NHẬT DƯ NỢ LUỸ KẾ TOÀN HỆ THỐNG ---
                        for u in st.session_state.users:
                            name = u['name']
                            if name == payer:
                                u['balance'] += (final_total_bill - current_shares.get(name, 0))
                            else:
                                u['balance'] -= current_shares.get(name, 0)
                            u['balance'] = int(round(u['balance']))
                            
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Lỗi phân tích hoặc định dạng hóa đơn từ AI: {e}")

# =========================================================================
# CỘT 3: THÔNG TIN CHI TIẾT ĐƠN HÀNG VÀ MÃ QR CHUYỂN KHOẢN TỰ ĐỘNG
# =========================================================================
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
        else:
            st.info("Không có ai nợ tiền đơn này.")
    else:
        st.info("Chưa có đơn hàng nào được quét.")
