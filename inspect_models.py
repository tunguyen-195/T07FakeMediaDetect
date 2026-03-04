
import os
import tensorflow as tf
from tensorflow.keras.models import load_model

MODEL_DIR = r"e:\Freelance\Research\D11_9_2025_Image_fixed_Detect\Project\T07FakeMediaDetect\webapp\models"
models_to_check = ["proposed_ela_50_casia_fidac.h5", "forgery_model_me.hdf5"]

print(f"TensorFlow Version: {tf.__version__}")

for model_name in models_to_check:
    path = os.path.join(MODEL_DIR, model_name)
    print(f"\n--- INSPECTING: {model_name} ---")
    if not os.path.exists(path):
        print("File not found.")
        continue
        
    try:
        model = load_model(path, compile=False) # Compile false cho nhanh
        print("Load thành công!")
        
        # Check input
        try:
            input_shape = model.input_shape
            print(f"Input Shape: {input_shape}")
        except:
            print("Input Shape: Unknown")
            
        # Check output
        try:
            output_shape = model.output_shape
            print(f"Output Shape: {output_shape}")
        except:
             print("Output Shape: Unknown")

        # Check layers count
        print(f"Total Layers: {len(model.layers)}")
        
        # Last layer config
        last_layer = model.layers[-1]
        print(f"Last Layer: {last_layer.name}, Activation: {last_layer.get_config().get('activation')}")

    except Exception as e:
        print(f"Lỗi khi load model: {e}")
