# 📜 Credits and Acknowledgments

## Original Project

This project is based on and extends the work from:

**IFAKE - Image/Video Forgery Detection Application**
- **Repository:** https://github.com/shraddhavijay/IFAKE
- **License:** MIT License
- **Authors:** 
  - Shraddha Pawar
  - Gaurangi Pradhan
  - Bhavin Goswami

### Research Paper

The original AI models and methodology are described in:

**"Image Forgery Detection and Classification Using Deep Learning and FIDAC Dataset"**
- **Published:** IEEE Explore
- **DOI:** https://ieeexplore.ieee.org/document/9862034
- **Dataset:** [FIDAC (Forged Images Detection And Classification)](https://ieee-dataport.org/documents/fidac-forged-images-detection-and-classification)

---

## T07FakeMediaDetect Enhancements

This fork (T07FakeMediaDetect) adds the following improvements:

### Code Improvements
- ✅ Fixed AV1 codec compatibility issues with video analysis
- ✅ Added H.264 video conversion utilities
- ✅ Improved error handling and user feedback
- ✅ Enhanced session management for video analysis
- ✅ Suppressed TensorFlow warnings for cleaner output
- ✅ Added comprehensive documentation and guides

### New Features
- ✅ Batch scripts for Windows (.bat files) for easy setup
- ✅ Status checking utilities
- ✅ Video codec conversion tools
- ✅ Enhanced README with detailed installation guides
- ✅ Security documentation (.env.example, SECURITY_NOTE.md)
- ✅ Git LFS support for large model files

### Documentation
- ✅ Comprehensive README in Vietnamese and English
- ✅ Model documentation (MODELS_GUIDE.md)
- ✅ Troubleshooting guides
- ✅ AV1 codec issue documentation
- ✅ Installation and deployment guides

### Project Rebranding
- Original: IFAKE_WebApp
- Updated: T07FakeMediaDetect
- Updated all references and comments in code
- Maintained compatibility with original functionality

---

## License Compliance

### Original License (MIT)

The original IFAKE project is licensed under the MIT License, which permits:
- ✅ Commercial use
- ✅ Modification
- ✅ Distribution
- ✅ Private use

**Requirements:**
- ✅ Include original license and copyright notice
- ✅ State changes made to the original work

### Our Compliance

We comply with the MIT License by:
1. **Including the original LICENSE** file in the repository
2. **Providing this CREDITS.md** file acknowledging the original authors
3. **Documenting all changes** made to the original codebase
4. **Maintaining attribution** to the original authors

---

## Third-Party Libraries

This project also uses the following open-source libraries:

### Core Frameworks
- **Django 3.2+** - BSD License
- **TensorFlow 2.6+** - Apache License 2.0
- **Keras 2.6+** - MIT License

### Image/Video Processing
- **OpenCV (cv2)** - Apache License 2.0
- **Pillow (PIL)** - HPND License
- **NumPy** - BSD License
- **scikit-image** - BSD License

### Utilities
- **pdf2image** - MIT License
- **Poppler** - GPL License (external dependency)

See `webapp/requirements.txt` for complete list of dependencies.

---

## AI Models Attribution

### Image Forgery Detection Model
- **Model:** ELA-CNN on CASIA & FIDAC datasets
- **Source:** Original IFAKE research paper
- **Training:** Shraddha Pawar, Gaurangi Pradhan, Bhavin Goswami
- **Weights:** `proposed_ela_50_casia_fidac.h5` (37.5 MB)

### Video Forgery Detection Model
- **Model:** CNN for video frame analysis
- **Source:** Original IFAKE research
- **Weights:** `forgery_model_me.hdf5` (272 MB)

### Image Segmentation Model
- **Model:** Segmentation network
- **Source:** Original IFAKE project
- **Weights:** `segmenter_weights.h5` (9.1 MB)

---

## Dataset Attribution

### FIDAC Dataset
- **Name:** FIDAC (Forged Images Detection And Classification)
- **Source:** IEEE Dataport
- **Authors:** Shraddha Pawar, Gaurangi Pradhan, Bhavin Goswami
- **URL:** https://ieee-dataport.org/documents/fidac-forged-images-detection-and-classification
- **Description:** Original camera-clicked images with tampered versions

### CASIA Dataset
- **Name:** CASIA TIDE v2.0 (Tampered Image Detection Evaluation)
- **Source:** Chinese Academy of Sciences' Institute of Automation
- **Description:** Benchmark dataset for image forgery detection

---

## Contact and Contributions

### Original Authors
For questions about the original IFAKE project:
- GitHub: https://github.com/shraddhavijay/IFAKE

### T07FakeMediaDetect
For questions about this enhanced version:
- Repository: https://github.com/tunguyen-195/T07FakeMediaDetect
- Maintainer: tunguyen-195

---

## Citation

If you use this project or the original IFAKE project in your research, please cite:

```bibtex
@inproceedings{pawar2022image,
  title={Image Forgery Detection and Classification Using Deep Learning and FIDAC Dataset},
  author={Pawar, Shraddha and Pradhan, Gaurangi and Goswami, Bhavin},
  booktitle={2022 IEEE Conference},
  year={2022},
  organization={IEEE},
  doi={10.1109/...9862034}
}
```

---

## Disclaimer

This project is provided "as is" without warranty of any kind. The detection results should be used as a reference only and not as definitive proof of forgery or authenticity.

For production use, additional verification and human expert review is recommended.

---

**Last Updated:** 2025-11-10  
**Version:** 1.0.0
