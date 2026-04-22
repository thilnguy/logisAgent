# 📘 Hướng dẫn sử dụng LogisAgent: Industrial Solver (Industrial)

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
4. **Cấu hình Expert (🚀 Optimisation Expert)**:
   - **Ensemble Mode (🤖)**: Bật chế độ đa luồng để AI chạy nhiều chiến lược cùng lúc.
   - **Workers Concurrents**: Số lượng nhân xử lý song song (1-8).
   - **Metaheuristic**: Lựa chọn thuật toán cấp cao (Tabu Search, Simulated Annealing) khi không dùng Ensemble.

### Bước 2: Nạp dữ liệu (Simuler hoặc Import)
1. **Lựa chọn chế độ**: Ở đầu thanh bên, mục **"Importation Industrielle"** cho phép bạn chọn:
   - **Chế độ Giả lập**: Tắt nút gạt "Activer Remplacement Manuel" và dùng thanh trượt để chọn số lượng đơn hàng.
   - **Chế độ Thủ công/Import**: Bật nút gạt "Activer Remplacement Manuel". Lúc này bạn có thể tải file CSV/Excel lên.
2. **Template**: Sử dụng nút **"Télécharger Template CSV"** để lấy file mẫu chuẩn.
3. **Chỉnh sửa trực tiếp**: Sau khi nạp dữ liệu, bạn có thể sửa trực tiếp Tọa độ, Khối lượng, Khung giờ và **Priority (Độ ưu tiên)** ngay trên bảng **"📋 WMS Data Feed & Éditeur Interactif"**.

### Bước 3: Thực thi tối ưu hóa
Nhấn nút **"🚀 Exécuter Solveur CVRPTW"**. 
- AI (Google OR-Tools) sẽ tính toán hàng triệu phương án để tìm ra lộ trình rẻ nhất và đúng giờ nhất dựa trên chiến lược bạn đã chọn.

### Bước 4: Phân tích kết quả
Sau khi AI chạy xong, kết quả sẽ hiển thị qua 4 tab chính:

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

#### 4. 🧬 Solver Quality Audit (Kiểm toán Thuật toán)
- Theo dõi chỉ số **Convergence (Hội tụ)** của các Workers.
- **Giải thích con số "Coût" (Hàm mục tiêu)**: Đây là điểm số tổng hợp của Khoảng cách (mét) + Thời gian + Chi phí kích hoạt xe. Con số này **càng thấp càng tốt**. 
- Hệ thống tự động chọn giải pháp có `Coût` thấp nhất để hiển thị.

---

## ⚠️ Lưu ý quan trọng

- **Đơn hàng bị bỏ (Dropped Orders)**: Nếu hệ thống hiển thị cảnh báo màu vàng kèm bảng "Commandes Non-Livrées", nghĩa là đơn đó có khung giờ giao quá ngắn hoặc trọng lượng quá lớn mà không xe nào đáp ứng được. Hãy nới lỏng cấu hình hoặc thêm xe.
- **Vùng lãnh thổ (Territory)**: Các xe PL (12t) và HGV (44t) được cấu hình ưu tiên chạy vùng NORTH hoặc SOUTH để tối ưu chuyên môn hóa.

---
