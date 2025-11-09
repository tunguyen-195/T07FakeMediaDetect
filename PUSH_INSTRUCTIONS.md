# 🚀 Hướng dẫn Push lên GitHub

## ⚡ Cách nhanh nhất - Dùng script có sẵn:

### Bước 1: Chạy script
```cmd
cd E:\Freelance\Research\D11_9_2025_Image_fixed_Detect\Project\T07FakeMediaDetect
push_to_github.bat
```

**Script sẽ tự động:**
1. ✅ Kiểm tra git đã cài chưa
2. ✅ Tạo commit với message đầy đủ
3. ✅ Set main branch
4. ✅ Add remote origin
5. ✅ Push lên GitHub

---

## 🔧 Hoặc làm thủ công:

### Bước 1: Mở Command Prompt/PowerShell
```cmd
cd E:\Freelance\Research\D11_9_2025_Image_fixed_Detect\Project\T07FakeMediaDetect
```

### Bước 2: Tạo commit
```bash
git commit -m "Initial commit: T07FakeMediaDetect - AI-powered Image/Video Forgery Detection System" -m "" -m "- Django web application for fake media detection" -m "- 3 AI models: Image ELA-CNN, Video Forgery Detection, Image Segmentation" -m "- Supports both image and video analysis" -m "- Fixed AV1 codec compatibility issues with H.264 conversion" -m "- Comprehensive documentation and setup guides" -m "- Batch scripts for easy installation and management"
```

### Bước 3: Set main branch
```bash
git branch -M main
```

### Bước 4: Add remote repository
```bash
git remote add origin https://github.com/tunguyen-195/T07FakeMediaDetect.git
```

### Bước 5: Push
```bash
git push -u origin main
```

---

## 🔐 Nếu gặp lỗi Authentication:

### Option 1: Personal Access Token (Khuyến nghị)
1. Vào GitHub → Settings → Developer settings → Personal access tokens
2. Generate new token (classic)
3. Chọn quyền: `repo` (full control)
4. Copy token
5. Khi push, dùng token làm password:
   - Username: `tunguyen-195`
   - Password: `<your-token>`

### Option 2: SSH Key
```bash
# Generate SSH key
ssh-keygen -t ed25519 -C "your-email@example.com"

# Add to ssh-agent
ssh-add ~/.ssh/id_ed25519

# Copy public key
cat ~/.ssh/id_ed25519.pub

# Add to GitHub → Settings → SSH and GPG keys

# Change remote to SSH
git remote set-url origin git@github.com:tunguyen-195/T07FakeMediaDetect.git
```

---

## ⚠️ Xử lý lỗi thường gặp:

### Lỗi: "remote origin already exists"
```bash
git remote remove origin
git remote add origin https://github.com/tunguyen-195/T07FakeMediaDetect.git
```

### Lỗi: "Repository already has commits"
```bash
git pull origin main --allow-unrelated-histories
git push -u origin main
```

### Lỗi: "failed to push some refs"
```bash
# If you're sure you want to overwrite
git push -u origin main --force
```

---

## ✅ Xác nhận đã push thành công:

1. **Mở browser:** https://github.com/tunguyen-195/T07FakeMediaDetect
2. **Kiểm tra:**
   - ✅ Files đã hiển thị
   - ✅ README.md hiển thị ở homepage
   - ✅ Commit history có 1 commit từ `tunguyen-195`
   - ✅ Không có thông tin về factory-droid

3. **Test clone:**
   ```bash
   cd /tmp
   git clone https://github.com/tunguyen-195/T07FakeMediaDetect.git
   cd T07FakeMediaDetect
   ls -la
   ```

---

## 📊 Thông tin Repository sau khi push:

- **Repository URL:** https://github.com/tunguyen-195/T07FakeMediaDetect
- **Clone URL (HTTPS):** https://github.com/tunguyen-195/T07FakeMediaDetect.git
- **Clone URL (SSH):** git@github.com:tunguyen-195/T07FakeMediaDetect.git
- **Author:** tunguyen-195
- **License:** MIT (nếu có)
- **Files:** 75 files
- **Models:** 3 AI models (~318 MB total)

---

## 📝 Note về Droid Shield:

Droid Shield phát hiện "potential secrets" nhưng đây là **false positives**:
- `README.md:1080` → Example documentation
- `Model_Training.ipynb` → Base64-encoded images

✅ **An toàn để commit!** Không có secrets thật trong repository.

---

## 🎯 Sau khi push thành công:

1. **Update README.md** trên GitHub (nếu cần)
2. **Add topics/tags:** machine-learning, deep-learning, forgery-detection, django
3. **Create releases** (optional)
4. **Enable GitHub Pages** cho documentation (optional)
5. **Add CI/CD workflows** (optional)

---

**Updated:** 2025-11-10  
**Repository:** https://github.com/tunguyen-195/T07FakeMediaDetect
