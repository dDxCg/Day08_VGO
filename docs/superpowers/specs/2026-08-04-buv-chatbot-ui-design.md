# Thiết kế UI/UX — BUV Student Services Chatbot

Ngày: 2026-08-04  
Giai đoạn: Prototype tĩnh để duyệt giao diện  
Phạm vi triển khai sau khi duyệt: `Day08_VGO/ui-design/prototype.html`

## 1. Định vị sản phẩm

Đây không phải chatbot tổng quát và không phải Research Agent. Đây là web chatbot song ngữ EN/VI, có trải nghiệm quen thuộc như ChatGPT nhưng chuyên trả lời thông tin BUV thuộc hai nhóm:

- Chính sách và quy định dịch vụ đại học: học phí, học bổng, ký túc xá, đăng ký học phần.
- Thông tin và thông báo đại học: sự kiện, dịch vụ thư viện, hỗ trợ sinh viên.

Sản phẩm phục vụ chung sinh viên, phụ huynh và người đang cân nhắc nhập học. Không có bước chọn vai trò hoặc phân luồng người dùng.

Hai câu hỏi giao diện phải trả lời được nhanh:

1. Câu trả lời này dựa trên tài liệu BUV nào?
2. Thông tin đã được xác minh hay hệ thống chưa có đủ bằng chứng?

## 2. Mục tiêu của giai đoạn prototype

Tạo một prototype HTML mở trực tiếp bằng trình duyệt để duyệt bố cục, hình ảnh, nội dung và các trạng thái trước khi kết nối pipeline RAG. Prototype được phép dùng logo BUV cục bộ đã có trong `ui-design/image/`; không tải tài nguyên mạng.

Prototype:

- Dùng dữ liệu minh họa được nhận diện rõ là dữ liệu mẫu.
- Không gọi API, không đọc `.env`, không chạy retrieval hoặc generation.
- Không sửa `app.py` và không sửa Task 9–10.
- Không mô phỏng tool log vì backend hiện không phải agent tool-calling.
- Mô phỏng trực quan luồng loading và streaming để duyệt trải nghiệm.

Data thật, nguồn BUV và các file liên quan sẽ được tích hợp ở giai đoạn sau.

## 3. Hướng thẩm mỹ

Phong cách là một cổng dịch vụ học thuật hiện đại: rõ ràng, đáng tin, tập trung nội dung và quen thuộc như ChatGPT. Giao diện không dùng phong cách dashboard kỹ thuật hoặc console nghiên cứu.

Điểm nhận diện:

- Màu nhấn chính: BUV Red `#D71F27`.
- Chữ trên nền đỏ: `#FFFFFF`.
- Theme Sáng dùng nền trắng, sidebar xám rất nhạt, chữ đen và xám đậm.
- Theme Tối dùng các token nền/chữ được đo tương phản riêng, không đảo màu tự động.
- Không dùng gradient trang trí trong prototype đầu tiên.
- Icon là SVG đơn sắc dùng `currentColor`; không dùng emoji nhiều màu làm icon chức năng.
- Nút icon ở trạng thái active/primary dùng nền `#D71F27`, glyph trắng.
- Trạng thái hệ thống luôn có icon và chữ, không truyền đạt chỉ bằng màu.
- Sidebar dùng logo chính thức tại `ui-design/image/Logo ĐH Anh Quốc Việt Nam -BUV.png`, giữ nguyên tỉ lệ và không recolor.

Font khai báo `Be Vietnam Pro`, sau đó fallback `Segoe UI`, `system-ui`, `sans-serif`. Prototype không tải font ngoài.

## 4. Bố cục tổng thể

### 4.1. Sidebar

Sidebar theo mô hình ChatGPT, rộng khoảng 260px trên desktop:

- Logo BUV chính thức và tên `BUV Assistant`; không hiện dòng phụ “Student Services Chatbot”.
- Nút “Cuộc trò chuyện mới” / “New chat”.
- Tìm kiếm lịch sử hội thoại.
- Danh sách hội thoại mẫu theo thời gian.
- Nút thu gọn sidebar.
- Footer tài khoản gồm avatar tròn đỏ chữ `G`, tên `Guest` và nút mở Settings.

Trên mobile, sidebar trở thành drawer có scrim và đóng được bằng phím Escape.

### 4.2. Header

Header gọn, luôn nhìn thấy:

- Tên `BUV Student Services Assistant`.
- Trạng thái sẵn sàng hoặc trạng thái lượt hiện tại.
- Công tắc `VI / EN`.
- Nút mở sidebar trên màn hình nhỏ.

Không hiển thị provider, model, API key hoặc thông tin kỹ thuật nội bộ trong prototype.

### 4.3. Settings

Settings mở trong modal có ba tab, đóng được bằng nút đóng, click scrim hoặc phím Escape. Modal giữ focus trong hộp khi mở và trả focus về nút kích hoạt khi đóng.

**Giao diện**

- Chủ đề: `Sáng`, `Tối`, `Hệ thống`; đổi ngay, không tải lại.
- Ngôn ngữ: đồng bộ với công tắc `VI / EN` trên header.
- `Hiện chi tiết truy xuất mặc định`: mở sẵn khối route/chunks/ngôn ngữ dưới phần nguồn. Đây là bản phù hợp RAG, thay cho “Hiện log tool mặc định” của mẫu Research Agent.

**Bộ nhớ giữa các phiên**

- Bật/tắt Memory.
- `Đã nhớ`: minh họa các sở thích phù hợp BUV như ngôn ngữ ưu tiên, cách trình bày câu trả lời và việc luôn hiện nguồn.
- Nút `Quản lý`.
- `Xoá toàn bộ Memory`, kèm mô tả không ảnh hưởng lịch sử hội thoại đã lưu.

**Dữ liệu & quyền riêng tư**

- Lưu hội thoại vào máy.
- Ẩn dữ liệu nhạy cảm trong nhật ký chẩn đoán.
- Hỏi trước khi thực hiện hành động bên ngoài chatbot hoặc gửi dữ liệu ra ngoài.
- Xoá toàn bộ hội thoại, có cảnh báo không hoàn tác được.

Theme và ngôn ngữ hoạt động thật trong prototype. Các toggle cần backend chỉ thay đổi trạng thái giao diện và hiện toast xác nhận; không được tuyên bố đã lưu dữ liệu thật.

### 4.4. Vùng hội thoại

- Nội dung giới hạn khoảng 820–880px để giữ độ dài dòng dễ đọc.
- Tin nhắn người dùng căn phải, nền xám nhạt.
- Phản hồi của chatbot căn trái, không đặt trong card nặng.
- Citation dạng `[1]`, `[2]` nằm sát khẳng định liên quan.
- Khối nguồn BUV nằm ngay dưới phản hồi, không chuyển sang một trang hoặc panel xa ngữ cảnh.

### 4.5. Composer

Composer cố định ở đáy vùng chat:

- Nút đính kèm.
- Textarea tự giãn.
- Nút gửi.
- Enter để gửi, Shift+Enter để xuống dòng.
- Dòng lưu ý: câu trả lời cần được đối chiếu với nguồn chính thức của BUV.

Trong Loading và Streaming, composer bị khóa. Nút gửi chuyển thành nút dừng phản hồi.

## 5. Màn hình rỗng

Màn hình rỗng có ba tầng:

1. Lời chào ngắn, mô tả chatbot chuyên về thông tin và dịch vụ BUV.
2. Phạm vi hỗ trợ và giới hạn: chỉ trả lời dựa trên nguồn BUV đã được cung cấp.
3. Sáu câu hỏi mẫu: học phí, học bổng, ký túc xá, đăng ký học phần, thư viện và sự kiện.

Câu hỏi mẫu chỉ điền nội dung vào composer để người dùng có thể sửa trước khi gửi.

## 6. Trạng thái giao diện

Prototype có thanh `KHUNG THỬ — không thuộc UI thật` để chuyển trạng thái. Sản phẩm thật sẽ tự điều khiển các trạng thái này.

### 6.1. Rỗng

Hiển thị lời chào, phạm vi và sáu câu hỏi mẫu.

### 6.2. Loading

- Loader chuyển động nhẹ.
- Nội dung: “Đang tìm trong tài liệu BUV…” / “Searching BUV documents…”.
- Giữ nguyên câu hỏi người dùng trên màn hình.
- Composer khóa; nút gửi đổi thành nút dừng.
- Không hiển thị tool log giả.

### 6.3. Streaming

- Nội dung phản hồi xuất hiện dần theo đoạn.
- Có con trỏ đang sinh ở cuối nội dung hiện tại.
- Citation xuất hiện cùng đoạn liên quan.
- Khối nguồn dùng skeleton giữ chỗ để tránh dịch chuyển bố cục.
- Toolbar phản hồi chưa hoạt động cho đến khi streaming hoàn tất.
- Nút dừng chuyển prototype sang trạng thái phản hồi đã dừng.

Streaming thật từ backend là phương án ưu tiên ở giai đoạn tích hợp. Nếu backend trả nguyên buffer, UI có thể trình bày buffer theo từng đoạn mà không thay đổi layout.

### 6.4. Hoàn tất

- Hiển thị câu trả lời đầy đủ và citation.
- Hiển thị khối nguồn đã hoàn thiện.
- Bật toolbar: sao chép, thích, không thích, tạo lại.
- Icon toolbar dùng SVG đơn sắc; nút đã chọn dùng nền đỏ và glyph trắng.

### 6.5. Không đủ bằng chứng

- Không đoán câu trả lời.
- Nêu rõ chưa thể xác minh từ nguồn hiện có.
- Gợi ý kiểm tra trang chính thức hoặc kênh liên hệ phù hợp của BUV.
- Vẫn hiển thị các nguồn đã truy xuất nếu có.

### 6.6. PageIndex fallback

- Trình bày phản hồi như trạng thái hoàn tất.
- Trong phần chi tiết truy xuất, ghi rõ route là `PageIndex` thay vì `Hybrid`.
- Route retrieval là metadata kỹ thuật phụ, không chiếm ưu tiên hơn nội dung và nguồn.

### 6.7. Lỗi hệ thống

- Thông báo bằng ngôn ngữ người dùng: chuyện gì xảy ra, dữ liệu nào được giữ và người dùng có thể làm gì tiếp theo.
- Giữ nguyên câu hỏi đã nhập.
- Có nút thử lại.
- Không hiển thị stack trace, đường dẫn máy, biến môi trường hoặc secret.

### 6.8. Đã dừng phản hồi

- Giữ phần nội dung đã stream.
- Gắn nhãn “Đã dừng” / “Stopped”.
- Cho phép tạo lại phản hồi.

## 7. Khối nguồn BUV

Khối `Nguồn BUV đã sử dụng` / `BUV sources used` nằm ngay dưới phản hồi.

Mỗi nguồn hiển thị:

- Số citation.
- Tên tài liệu hoặc thông báo.
- Nhóm `Chính sách/Quy định` hoặc `Thông tin/Thông báo`.
- Ngày cập nhật nếu metadata có cung cấp.
- Điểm liên quan nếu backend có cung cấp.
- Nút mở nguồn.

Các giá trị chưa tồn tại trong contract hiện tại không được tự suy diễn. Prototype chỉ minh họa hình dạng component; giai đoạn tích hợp sẽ ánh xạ từ `metadata.source`, `metadata.type`, `score` và các field thật được bổ sung.

## 8. Song ngữ EN/VI

- Công tắc `VI / EN` đổi toàn bộ nhãn giao diện, placeholder, banner, câu hỏi mẫu và nội dung minh họa.
- Chuyển ngôn ngữ không làm mất hội thoại đang xem.
- Prototype không tự động dịch dữ liệu hoặc kết quả backend.
- Giai đoạn tích hợp phải truyền lựa chọn ngôn ngữ vào generation thay vì dịch lại câu trả lời ở frontend.

## 9. Thành phần tương tác

- Sidebar đóng/mở.
- Chọn hội thoại mẫu.
- Nút câu hỏi mẫu điền composer.
- Textarea tự giãn.
- VI/EN toggle.
- Mở/đóng Settings bằng nút ở footer tài khoản.
- Chuyển Sáng/Tối/Hệ thống và phản ứng với thay đổi theme hệ điều hành khi đang ở chế độ Hệ thống.
- Đồng bộ ngôn ngữ giữa header và Settings.
- Bật/tắt các switch Settings ở mức prototype.
- Thanh chuyển trạng thái prototype.
- Mở/đóng khối nguồn và chi tiết truy xuất.
- Sao chép phản hồi.
- Thích/không thích loại trừ lẫn nhau.
- Dừng streaming mô phỏng.
- Thử lại từ trạng thái lỗi.

Các nút chỉ có icon đều phải có `aria-label` và tooltip.

## 10. Responsive và accessibility

- Kiểm ở 375px, 768px và 1440px.
- Không cuộn ngang toàn trang.
- Bảng hoặc nội dung dài chỉ cuộn trong hộp riêng.
- Vùng bấm tối thiểu 44×44px.
- Chữ nội dung tối thiểu 15–16px, line-height tối thiểu 1.5.
- Tương phản chữ thường tối thiểu 4.5:1.
- Focus bàn phím rõ và không bị loại bỏ.
- Các control tùy biến có role, state và label tương ứng.
- Hỗ trợ `prefers-reduced-motion`; dừng loader và transition không thiết yếu.
- Phóng to 200% vẫn sử dụng được.

## 11. Cấu trúc file

Giai đoạn prototype chỉ tạo:

```text
Day08_VGO/
└── ui-design/
    ├── prototype.html
    └── image/
        └── Logo ĐH Anh Quốc Việt Nam -BUV.png
```

HTML tự chứa CSS, SVG icon, JavaScript và dữ liệu mẫu; chỉ tham chiếu logo PNG cục bộ ở trên. Không dùng CDN hoặc tài nguyên mạng.

Giai đoạn tích hợp Streamlit sau khi prototype được duyệt mới xem xét tách thành:

```text
Day08_VGO/
├── app.py
└── ui/
    ├── theme.py
    ├── state.py
    ├── components.py
    └── sources.py
```

## 12. Tiêu chí nghiệm thu prototype

Prototype đạt khi:

1. Mở trực tiếp `prototype.html` trong trình duyệt mà không cần server.
2. Chuyển được các trạng thái Rỗng, Loading, Streaming, Hoàn tất, Không đủ bằng chứng, PageIndex fallback, Lỗi và Đã dừng.
3. Chuyển VI/EN không làm vỡ bố cục hoặc mất trạng thái đang xem.
4. Loading và Streaming có hình thái khác nhau rõ ràng.
5. Streaming giữ chỗ cho nguồn, không gây nhảy bố cục lớn khi hoàn tất.
6. Sidebar hoạt động trên desktop và mobile.
7. Toolbar dùng icon đơn sắc; trạng thái chọn hiển thị nền `#D71F27`, glyph trắng.
8. Không có emoji nhiều màu trong vai trò icon chức năng.
9. Không có API key, `.env`, đường dẫn tuyệt đối, stack trace hoặc dữ liệu thật trên màn hình.
10. Không có cuộn ngang ở 375px, 768px và 1440px.
11. Logo BUV hiển thị đúng tỉ lệ; dòng “Student Services Chatbot” không còn xuất hiện.
12. Footer sidebar hiển thị avatar `G`, tên `Guest` và mở được Settings.
13. Modal Settings có đủ ba tab Giao diện, Bộ nhớ, Dữ liệu & quyền riêng tư.
14. Sáng/Tối/Hệ thống đổi ngay; Hệ thống bám theo `prefers-color-scheme`.
15. VI/EN trong Settings đồng bộ hai chiều với header.
16. Các toggle prototype đổi trạng thái và không tuyên bố đã ghi dữ liệu thật.

## 13. Ngoài phạm vi

Giai đoạn này cố ý không làm:

- Kết nối data thật hoặc nguồn BUV thật.
- Sửa và chạy retrieval/generation Task 9–10.
- Lưu lịch sử hội thoại thật.
- Đăng nhập hoặc phân vai người dùng.
- Voice input thật, upload file thật hoặc gửi feedback thật.
- Lưu thật các lựa chọn Settings, Memory hoặc transcript vào backend.
- Tool log hoặc các trạng thái chỉ tồn tại ở agent tool-calling.
- Dashboard evaluation và so sánh cấu hình RAG.

Các mục này chỉ được bổ sung sau khi giao diện prototype được duyệt và backend có contract tương ứng.
