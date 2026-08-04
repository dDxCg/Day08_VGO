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

Tạo một file HTML độc lập để duyệt bố cục, hình ảnh, nội dung và các trạng thái trước khi kết nối pipeline RAG.

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
- Nền chính trắng, sidebar xám rất nhạt, chữ đen và xám đậm.
- Không dùng gradient trang trí trong prototype đầu tiên.
- Icon là SVG đơn sắc dùng `currentColor`; không dùng emoji nhiều màu làm icon chức năng.
- Nút icon ở trạng thái active/primary dùng nền `#D71F27`, glyph trắng.
- Trạng thái hệ thống luôn có icon và chữ, không truyền đạt chỉ bằng màu.

Font khai báo `Be Vietnam Pro`, sau đó fallback `Segoe UI`, `system-ui`, `sans-serif`. Prototype không tải font ngoài.

## 4. Bố cục tổng thể

### 4.1. Sidebar

Sidebar theo mô hình ChatGPT, rộng khoảng 260px trên desktop:

- Nhận diện BUV và tên chatbot.
- Nút “Cuộc trò chuyện mới” / “New chat”.
- Tìm kiếm lịch sử hội thoại.
- Danh sách hội thoại mẫu theo thời gian.
- Nút thu gọn sidebar.

Trên mobile, sidebar trở thành drawer có scrim và đóng được bằng phím Escape.

### 4.2. Header

Header gọn, luôn nhìn thấy:

- Tên `BUV Student Services Assistant`.
- Trạng thái sẵn sàng hoặc trạng thái lượt hiện tại.
- Công tắc `VI / EN`.
- Nút mở sidebar trên màn hình nhỏ.

Không hiển thị provider, model, API key hoặc thông tin kỹ thuật nội bộ trong prototype.

### 4.3. Vùng hội thoại

- Nội dung giới hạn khoảng 820–880px để giữ độ dài dòng dễ đọc.
- Tin nhắn người dùng căn phải, nền xám nhạt.
- Phản hồi của chatbot căn trái, không đặt trong card nặng.
- Citation dạng `[1]`, `[2]` nằm sát khẳng định liên quan.
- Khối nguồn BUV nằm ngay dưới phản hồi, không chuyển sang một trang hoặc panel xa ngữ cảnh.

### 4.4. Composer

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
    └── prototype.html
```

File này tự chứa HTML, CSS, SVG icon, JavaScript và dữ liệu mẫu. Không dùng CDN hoặc tài nguyên mạng.

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

## 13. Ngoài phạm vi

Giai đoạn này cố ý không làm:

- Kết nối data thật hoặc nguồn BUV thật.
- Sửa và chạy retrieval/generation Task 9–10.
- Lưu lịch sử hội thoại thật.
- Đăng nhập hoặc phân vai người dùng.
- Voice input thật, upload file thật hoặc gửi feedback thật.
- Dark mode.
- Tool log hoặc các trạng thái chỉ tồn tại ở agent tool-calling.
- Dashboard evaluation và so sánh cấu hình RAG.

Các mục này chỉ được bổ sung sau khi giao diện prototype được duyệt và backend có contract tương ứng.
