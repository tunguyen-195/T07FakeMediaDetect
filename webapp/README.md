# 🔍 T07FakeMediaDetect

> **AI-Powered Image & Video Forgery Detection System**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![Django 4.0+](https://img.shields.io/badge/django-4.0+-green.svg)](https://www.djangoproject.com/)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.x-orange.svg)](https://www.tensorflow.org/)

A modern, professional web application for detecting image and video forgeries using Deep Learning and advanced forensic techniques.

---

## 🌟 Features

### **Core Detection**
- 🤖 **Deep Learning Analysis**: CNN-based forgery detection using ELA (Error Level Analysis)
- 📸 **Multi-Format Support**: Analyze images (JPG, PNG), videos (MP4, AVI), and PDFs
- ⚡ **Real-time Processing**: Fast analysis with GPU acceleration support
- 🎯 **High Accuracy**: Trained on FIDAC and CASIA datasets

### **Forensic Tools**
- 🔬 **Error Level Analysis (ELA)**: Detect image compression inconsistencies
- 🌈 **Luminance Gradient**: Identify lighting inconsistencies
- 🔲 **Edge Detection**: Highlight suspicious boundaries
- 📊 **Noise Analysis**: Detect noise pattern inconsistencies
- 🔄 **Copy-Move Detection**: Find duplicated regions
- 📝 **Metadata Extraction**: View EXIF and file information

### **User Interface**
- 🎨 **Modern Design**: Clean cyan/blue professional theme
- 📱 **Fully Responsive**: Works on desktop, tablet, and mobile
- 🇻🇳 **Vietnamese Interface**: Localized for Vietnamese users
- 🖼️ **Image Zoom**: Click to zoom forensic analysis results
- 📊 **Clear Results**: Visual indicators for fake/real classification

---

## 🚀 Quick Start

### **Prerequisites**
- Python 3.8 or higher
- pip package manager
- (Optional) CUDA-compatible GPU for faster processing

### **Installation**

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/T07FakeMediaDetect.git
cd T07FakeMediaDetect/T07FakeMediaDetect
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Download AI models**

Download the pre-trained models and place them in the `models/` folder:
- [Image Detection Model](https://drive.google.com/drive/folders/1B4ODeK_QQ6XMFo6i6EEup1nZC6PllVfu)
- [Video Detection Model](https://drive.google.com/drive/folders/1irYZbRnr4Y7jKieSyhjxHxwk43oSMqh-)

```bash
# Create models directory if it doesn't exist
python -c "import os; os.makedirs('models', exist_ok=True)"
```

4. **Initialize database**
```bash
python manage.py migrate
```

5. **Run the application**

**Windows:**
```bash
start.bat
```

**Linux/Mac:**
```bash
python manage.py runserver 0.0.0.0:8001
```

6. **Access the application**

Open your browser and navigate to: `http://127.0.0.1:8001`

---

## 📚 Usage

### **Image Analysis**
1. Navigate to "Phân tích Ảnh" (Image Analysis)
2. Upload an image (JPG, PNG)
3. View AI prediction (Fake/Real with confidence score)
4. Use forensic tools to analyze specific aspects
5. Check metadata information

### **Video Analysis**
1. Navigate to "Phân tích Video" (Video Analysis)
2. Upload a video (MP4, AVI)
3. System extracts frames and analyzes each
4. View aggregated results

### **PDF Analysis**
1. Navigate to "Phân tích PDF"
2. Upload a PDF document
3. System extracts embedded images
4. Analyzes each image for forgery

---

## 🏗️ Project Structure

```
T07FakeMediaDetect/
├── T07FakeMediaDetect/          # Django project configuration
│   ├── __init__.py
│   ├── settings.py              # Django settings
│   ├── urls.py                  # URL routing
│   ├── wsgi.py                  # WSGI configuration
│   └── asgi.py                  # ASGI configuration
├── website/                     # Main application
│   ├── ImageForgeryDetection/   # Detection algorithms
│   │   ├── FakeImageDetector.py # Main detector class
│   │   └── forensics.py         # Forensic tools
│   ├── views.py                 # View handlers
│   ├── urls.py                  # App URLs
│   └── models.py                # Database models
├── static/                      # Static files
│   └── assets/
│       ├── css/                 # Stylesheets
│       │   └── style_v2.css     # Main stylesheet
│       ├── js/                  # JavaScript
│       └── img/                 # Images
├── templates/                   # HTML templates
│   ├── index.html               # Homepage
│   ├── image.html               # Image analysis
│   ├── video.html               # Video analysis
│   └── pdf.html                 # PDF analysis
├── models/                      # AI model files
│   ├── image_model.h5
│   └── video_model.h5
├── media/                       # User uploads (gitignored)
├── docs/                        # Documentation
│   ├── INSTALLATION.md
│   ├── TROUBLESHOOTING.md
│   └── API.md
├── manage.py                    # Django management
├── requirements.txt             # Python dependencies
├── start.bat                    # Windows start script
├── stop.bat                     # Windows stop script
├── restart.bat                  # Windows restart script
└── status.bat                   # Windows status check
```

---

## 🧪 Technology Stack

### **Backend**
- **Framework**: Django 4.x
- **Language**: Python 3.8+
- **AI/ML**: TensorFlow 2.x, Keras
- **Image Processing**: OpenCV, PIL, NumPy
- **PDF Processing**: pdf2image, Poppler

### **Frontend**
- **HTML5** with semantic markup
- **CSS3** with modern features (Grid, Flexbox, Animations)
- **JavaScript** (ES6+)
- **Bootstrap 5** for base components
- **Custom CSS** for professional design

### **Database**
- **Development**: SQLite3
- **Production**: PostgreSQL/MySQL (configurable)

---

## 📊 Performance

- **Image Analysis**: ~2-5 seconds per image
- **Video Analysis**: ~10-30 seconds (depends on duration and FPS)
- **PDF Analysis**: ~5-15 seconds (depends on embedded images)
- **Supported Image Formats**: JPG, JPEG, PNG
- **Supported Video Formats**: MP4, AVI, MOV
- **Max Upload Size**: 100MB (configurable)

---

## 🎨 Screenshots

### Homepage
![Homepage](screenshots/homepage.png)

### Image Analysis
![Image Analysis](screenshots/image_analysis.png)

### Forensic Tools
![Forensic Tools](screenshots/forensic_tools.png)

### Results Display
![Results](screenshots/results.png)

---

## 📖 Documentation

- [Installation Guide](docs/INSTALLATION.md)
- [User Guide](docs/USER_GUIDE.md)
- [Troubleshooting](TROUBLESHOOTING.md)
- [Testing Guide](TESTING_GUIDE.md)
- [API Documentation](docs/API.md)

---

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) first.

### **How to Contribute**
1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](../LICENSE) file for details.

---

## 👥 Credits

### **Original IFAKE Project**
- Shraddha Pawar
- Gaurangi Pradhan  
- Bhavin Goswami

**Research Paper**: [Image Forgery Detection and Classification Using Deep Learning and FIDAC Dataset](https://ieeexplore.ieee.org/document/9862034) (IEEE)

**Dataset**: [FIDAC - Forged Images Detection And Classification](https://ieee-dataport.org/documents/fidac-forged-images-detection-and-classification) (IEEE Dataport)

### **T07 Enhanced Version**
- Complete UI/UX redesign
- Modern responsive interface
- Enhanced forensic tools
- Improved performance and stability
- Comprehensive documentation

---

## 🔧 Configuration

### **Environment Variables**
Create a `.env` file in the project root:

```env
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
```

### **Settings**
Edit `T07FakeMediaDetect/settings.py` for:
- Database configuration
- Static files settings
- Media upload limits
- Security settings

---

## 🐛 Known Issues

- Large video files (>500MB) may cause timeout
- GPU detection works best with CUDA 11.x
- PDF processing requires Poppler to be installed

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for solutions.

---

## 📧 Support

For questions, issues, or feature requests:
- Open an issue on GitHub
- Check existing documentation
- Review troubleshooting guide

---

## ⭐ Star History

If you find this project useful, please consider giving it a star!

[![Star History Chart](https://api.star-history.com/svg?repos=yourusername/T07FakeMediaDetect&type=Date)](https://star-history.com/#yourusername/T07FakeMediaDetect&Date)

---

## 🗺️ Roadmap

- [ ] Add support for more image formats (WebP, HEIC)
- [ ] Implement batch processing
- [ ] Add API endpoints for programmatic access
- [ ] Create Docker containerization
- [ ] Add user authentication system
- [ ] Implement analysis history
- [ ] Add export reports (PDF, JSON)
- [ ] Multi-language support (English, Vietnamese)

---

<p align="center">
  Made with ❤️ by T07 Team
</p>

<p align="center">
  <a href="#-t07fakemediadetect">Back to top</a>
</p>
