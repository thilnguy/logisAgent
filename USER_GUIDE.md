# 📘 Hướng dẫn sử dụng LogisAgent V7

Chào mừng bạn đến với hệ thống Hỗ trợ Ra quyết định (Decision Support System - DSS) dành cho Trung tâm Logistics Orléans. Hệ thống này giúp bạn tối ưu hóa việc phân hành trình, quản lý đội xe và kiểm soát chi phí (TCO).

---

## 🚀 Quy trình 4 bước cơ bản

### Bước 1: Cấu hình tham số (Sidebar - Thanh bên trái)
Trước khi chạy tối ưu hóa, bạn cần thiết lập các điều kiện vận hành:
1. **Volume de commandes**: Chọn số lượng đơn hàng muốn giả lập (5 - 15 đơn).
2. **Live API (Bison Futé)**: Kiểm tra thông tin giao thông thời gian thực. Hệ thống sẽ tự động điều chỉnh tốc độ nếu trục đường A10 phía Bắc bị tắc nghẽn.
3. **Chiến lược quyết định (🎯 Stratégie)**:
   - **Économique (Tối ưu tiền)**: Gom đơn vào ít xe nhất, ưu tiên xe nhỏ nhất có thể.
   - **Équilibré (Cân bằng)**: Cấu hình mặc định, cân đối giữa chi phí và tải trọng.
   - **Social (Công bằng)**: Chia đều đơn hàng cho tất cả tài xế đang sẵn sàng.
   - *Mẹo: Bạn có thể mở mục "Cấu hình Trade-offs" để tinh chỉnh thủ công các trọng số.*

### Bước 2: Nạp dữ liệu (Simuler hoặc Import)
1. **Simulation**: Nhấn nút **"📦 Simuler Flux Entrant (WMS)"** để tạo dữ liệu giả lập.
2. **Import Industrial**: Mở mục "Importation Industrielle" ở thanh bên.
   - Bạn có thể tải file CSV/Excel của mình lên.
   - Có nút tải **Template** để bạn điền đúng định dạng.
3. **Chỉnh sửa trực tiếp**: Toàn bộ đơn hàng (từ giả lập hoặc file) sẽ hiện trong bảng **📋 WMS Data Feed & Éditeur Interactif**. Bạn có thể sửa trực tiếp Tọa độ, Khối lượng, Khung giờ ngay trên bảng này. Hệ thống AI sẽ tự động cập nhật theo dữ liệu mới nhất.

### Bước 3: Thực thi tối ưu hóa
Nhấn nút **"🚀 Exécuter Solveur CVRPTW"**. 
- AI (Google OR-Tools) sẽ tính toán hàng triệu phương án để tìm ra lộ trình rẻ nhất và đúng giờ nhất dựa trên chiến lược bạn đã chọn.

### Bước 4: Phân tích kết quả
Sau khi AI chạy xong, kết quả sẽ hiển thị qua 3 tab chính:

#### 1. 🌐 Digital Twin (Bản đồ)
- Hiển thị các cung đường di chuyển bằng đường vòng cung (Arc).
- **Màu sắc chấm tròn (Zones):**
  - 🔴 Đỏ: Kho hàng (Depot).
  - 🔵 Xanh dương: Vùng phía Bắc (NORTH).
  - 🟢 Xanh lá: Vùng phía Nam (SOUTH).
  - 🟠 Cam: Nội đô Orléans (CITY).
- Giúp bạn xác minh nhanh xe có chạy đúng vùng được giao hay không.

#### 2. 📊 Timeline Gantt (Lịch trình)
- Theo dõi chi tiết từng phút của từng tài xế.
- **Màu xanh dương**: Đang lái xe.
- **Màu xanh lá**: Đang giao hàng tại khách.
- **Màu xám**: Thời gian chờ (đến sớm trước giờ khách mở cửa).
- **Màu vàng (Pause)**: Nghỉ 45 phút bắt buộc (nếu tài xế lái liên tục > 4.5h theo luật EU).

#### 3. 💶 Financial Audit (Kiểm toán TCO)
- Bảng kê chi phí chi tiết từng xe: Tiền dầu, Tiền lương, Phí bảo dưỡng, Thuế CO2 và **Phí kích hoạt xe**.
- Cột **Taux Chargement (%)**: Cho biết xe đó đã đầy bao nhiêu %. Nếu tỷ lệ này thấp (< 50%), hãy cân nhắc chuyển sang chiến lược "Économique".

---

## ⚠️ Lưu ý quan trọng

- **Đơn hàng bị bỏ (Dropped Orders)**: Nếu hệ thống hiển thị cảnh báo màu vàng kèm bảng "Commandes Non-Livrées", nghĩa là đơn đó có khung giờ giao quá ngắn hoặc trọng lượng quá lớn mà không xe nào đáp ứng được. Hãy nới lỏng cấu hình hoặc thêm xe.
- **Vùng lãnh thổ (Territory)**: Các xe PL (12t) và HGV (44t) được cấu hình ưu tiên chạy vùng NORTH hoặc SOUTH để tối ưu chuyên môn hóa.

---
