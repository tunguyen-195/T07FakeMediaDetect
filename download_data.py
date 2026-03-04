
import os
import subprocess
import zipfile
import shutil

# Cấu hình
DATASET_DIR = r"e:\Freelance\Research\D11_9_2025_Image_fixed_Detect\Project\T07FakeMediaDetect\Datasets"
CASIA_KAGGLE_ID = "divg07/casia-20-image-tampering-detection-dataset"
# FIDAC không có trên Kaggle, cần tải thủ công hoặc tìm nguồn khác
# Tuy nhiên ta cứ tạo thư mục sẵn

def create_dirs():
    if not os.path.exists(DATASET_DIR):
        os.makedirs(DATASET_DIR)
        print(f"Created directory: {DATASET_DIR}")
    
    fidac_dir = os.path.join(DATASET_DIR, "FIDAC")
    if not os.path.exists(fidac_dir):
        os.makedirs(fidac_dir)
        print(f"Created directory: {fidac_dir}")
        with open(os.path.join(fidac_dir, "README.txt"), "w", encoding="utf-8") as f:
            f.write("FIDAC Dataset chưa có sẵn trên Kaggle công khai.\n")
            f.write("Vui lòng tải từ IEEE Dataport: https://ieee-dataport.org/documents/fidac-forged-images-detection-and-classification\n")
            f.write("Sau khi tải về, giải nén và đặt các thư mục con (Original, Forged) vào đây.")

def download_casia():
    print("Downloading CASIA 2.0 Dataset from Kaggle...")
    try:
        # Kiểm tra kaggle đã cài chưa
        subprocess.run(["kaggle", "--version"], check=True, stdout=subprocess.PIPE)
        
        # Tải dataset
        cmd = ["kaggle", "datasets", "download", "-d", CASIA_KAGGLE_ID, "-p", DATASET_DIR, "--unzip"]
        print(f"Running command: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        print("Download and unzip completed successfully.")
        
        # Xử lý sau khi tải (Kaggle thường giải nén vào thư mục con hoặc flatten)
        # Check structure
        print("Checking dataset structure...")
        for root, dirs, files in os.walk(DATASET_DIR):
            level = root.replace(DATASET_DIR, '').count(os.sep)
            indent = ' ' * 4 * (level)
            print(f'{indent}{os.path.basename(root)}/')
            subindent = ' ' * 4 * (level + 1)
            # print first 2 files
            for f in files[:2]:
                print(f'{subindent}{f}')
                
    except FileNotFoundError:
        print("Error: 'kaggle' command not found. Please install Kaggle CLI (pip install kaggle) and setup API key.")
    except subprocess.CalledProcessError as e:
        print(f"Error downloading dataset: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    create_dirs()
    download_casia()
