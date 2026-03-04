import os
import ctypes
try:
    from keras.models import load_model  # type: ignore
except Exception:
    load_model = None
import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageFilter
# import PIL.ImageQt
import cv2 as cv
from matplotlib import pyplot as plt
from website.ImageForgeryDetection.NeuralNets import initClassifier, initSegmenter
from skimage import feature
import joblib

# Import module Benford
try:
    from website.ImageForgeryDetection.benford_analysis import extract_benford_features
except ImportError:
    print("Warning: benford_analysis module not found. Hybrid mode unavailable.")
    extract_benford_features = None

# Color-image denoising
from skimage.restoration import (denoise_wavelet,estimate_sigma)
from skimage.util import random_noise
import skimage.io

resaved_filename = os.path.join(os.getcwd(), 'media', 'tempresaved.jpg')
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# Model Paths
DEFAULT_MODEL_PATH = os.path.join(PROJECT_ROOT, 'models', 'proposed_ela_50_casia_fidac.h5')
DEFAULT_SEGMENTER_WEIGHTS = os.path.join(PROJECT_ROOT, 'models', 'segmenter_weights.h5')
DEFAULT_SVM_PATH = os.path.join(PROJECT_ROOT, 'models', 'hybrid_svm_model.pkl')
DEFAULT_SCALER_PATH = os.path.join(PROJECT_ROOT, 'models', 'hybrid_scaler.pkl')


class FID: 
   
   def prepare_image(self,fname):
    image_size = (128, 128)
    return  np.array(self.convert_to_ela_image(fname,90).resize(image_size)).flatten() / 255.0

   def predict_result(self,fname):
      print("=== PREDICTING RESULT ===")
      # 1. Load CNN Model
      if load_model is None or not os.path.exists(DEFAULT_MODEL_PATH):
         print("Model CNN not found.")
         return ('Authentic', '0.00')

      model = load_model(DEFAULT_MODEL_PATH)
      
      # 2. Extract CNN Prob
      try:
          test_image = self.prepare_image(fname)
          test_image = test_image.reshape(-1, 128, 128, 3)
          y_pred = model.predict(test_image)
          cnn_prob = y_pred[0][0] # P(Class 1 = Forged) in CNN
          print(f"CNN Raw Prob (Forged): {cnn_prob}")
      except Exception as e:
          print(f"Error predicting CNN: {e}")
          return ('Error', '0.00')

       # 3. Hybrid Mode Check
      if os.path.exists(DEFAULT_SVM_PATH) and os.path.exists(DEFAULT_SCALER_PATH) and extract_benford_features:
          try:
              print("=== RUNNING HYBRID ANALYSIS (CNN + BENFORD) ===")
              
              # Try loading SVM model (may fail if saved with different NumPy version)
              try:
                  svm = joblib.load(DEFAULT_SVM_PATH)
                  scaler = joblib.load(DEFAULT_SCALER_PATH)
              except ModuleNotFoundError as e:
                  if 'numpy._core' in str(e) or 'numpy.core' in str(e):
                      print(f"NumPy version mismatch: Model was saved with NumPy 2.x but running with NumPy 1.x")
                      print("Solution: Run 'pip install numpy --upgrade' in the venv, OR re-train the model with current NumPy.")
                      raise
                  raise
              
              # Extract Benford
              benford_feats = extract_benford_features(fname)
              
              # Combine [CNN_Prob, Benford]
              combined_features = np.hstack(([cnn_prob], benford_feats)).reshape(1, -1)
              
              # Scale
              scaled_features = scaler.transform(combined_features)
              
              # Predict SVM (P(Forged))
              # SVM Classes: 0=Authentic, 1=Forged
              svm_probs = svm.predict_proba(scaled_features)[0]
              prob_forged = svm_probs[1] # Probability of Class 1
              
              print(f"Hybrid SVM Prob (Forged): {prob_forged}")
              
              if prob_forged > 0.5:
                  prediction = 'Forged'
                  confidence = f'{prob_forged * 100:0.2f}'
              else:
                  prediction = 'Authentic'
                  confidence = f'{(1 - prob_forged) * 100:0.2f}'
                  
              print(f"Hybrid Result: {prediction} ({confidence}%)")
              return (prediction, confidence)
              
          except Exception as e:
              print(f"Hybrid Failed: {e}. Fallback to CNN.")

      # 4. Fallback (CNN Only)
      print("=== FALLBACK TO CNN ONLY ===")
      
      # Logic: 0=Forged ?? WAIT.
      # Original code: 
      # class_names = ['Forged', 'Authentic'] (Index 0=Forged, 1=Authentic)
      # y_pred_class = int(round(y_pred[0][0]))
      # If y_pred ~ 0 -> Index 0 -> Forged ?
      # If y_pred ~ 1 -> Index 1 -> Authentic ?
      #
      # BUT my Hybrid Notebook used: 0=Authentic, 1=Forged.
      # This is conflicting.
      # Let's trust the Original Code Logic for Fallback.
      # Original: If <= 0.5 -> Forged. If > 0.5 -> Authentic.
      
      class_names = ['Forged', 'Authentic']
      y_pred_val = y_pred[0][0]
      
      if y_pred_val <= 0.5:
         # <= 0.5 -> Forged (Class 0)
         prediction = 'Forged'
         confidence = f'{(1-y_pred_val) * 100:0.2f}'
      else:
         # > 0.5 -> Authentic (Class 1)
         prediction = 'Authentic'
         confidence = f'{(y_pred_val) * 100:0.2f}'
         
      print(f"CNN Result: {prediction} ({confidence}%)")
      return (prediction, confidence)


   def genMask(self,file_path):
      segmenter=initSegmenter()
      if os.path.exists(DEFAULT_SEGMENTER_WEIGHTS):
         segmenter.load_weights(DEFAULT_SEGMENTER_WEIGHTS)
      else:
         print("Segmenter weights not found.")
         return None
         
      testimg=self.convert_to_ela_image(file_path,90).resize((256,256))
      testimg=testimg.getchannel('B')
      test=np.array(testimg)/np.max(testimg)
      test=test.reshape(-1,256,256,1)
      mask=segmenter.predict(test)
      mask=mask.reshape(256,256)
      mask=(mask*255).astype('uint8')
      mask_im = Image.fromarray(mask)
      mask_im.save(resaved_filename, 'JPEG')
      return mask_im


   def convert_to_ela_image(self,path,quality):
      try:
          import urllib.parse
          decoded_path = urllib.parse.unquote(path)
          decoded_path = os.path.abspath(decoded_path)
          print('-----------path--------------',decoded_path)
          original_image = Image.open(decoded_path).convert('RGB')

          resaved_file_name = resaved_filename  
          original_image.save(resaved_file_name,'JPEG',quality=quality)
          resaved_image = Image.open(resaved_file_name)

          ela_image = ImageChops.difference(original_image,resaved_image)
          
          extrema = ela_image.getextrema()
          max_difference = max([pix[1] for pix in extrema])
          if max_difference ==0:
             max_difference = 1
          scale = 255.0 / max_difference
          
          ela_image = ImageEnhance.Brightness(ela_image).enhance(scale)
          return ela_image
      except Exception as e:
          print(f"ELA Error: {e}")
          return Image.new('RGB', (128, 128))


   def show_ela(self, file_path,sl=50):
      ela_im=self.convert_to_ela_image(file_path, 90)
      ela_im.save(resaved_filename, 'JPEG')
      return ela_im


   def detect_edges(self, path):
      import urllib.parse
      decoded_path = urllib.parse.unquote(path)
      image = Image.open(decoded_path)   
      image = image.convert("L") 
      image = image.filter(ImageFilter.FIND_EDGES)
      image = np.array(image.resize((256,256)))
      edge_im = Image.fromarray(image)
      edge_im.save(resaved_filename, 'JPEG')
      return edge_im

   def luminance_gradient(self, path):
      import urllib.parse
      decoded_path = urllib.parse.unquote(path)
      decoded_path = os.path.abspath(decoded_path)
      resaved_filename_png = os.path.join(os.getcwd(), 'media', 'luminance_gradient.png')
      img = cv.imread(decoded_path, 0)
      if img is None: return Image.new('L', (600,600))
      sobelx = cv.Sobel(img,cv.CV_64F,1,0,ksize=15)
      sobelx_norm = np.uint8(np.absolute(sobelx))
      image = Image.fromarray(sobelx_norm).resize((600,600))
      image.save(resaved_filename_png, 'PNG')
      return image

   def noise_analysis(self, path, quality, intensity):
      import urllib.parse
      filename = urllib.parse.unquote(path)
      filename = os.path.abspath(filename)
      resaved_filename = 'tempresaved.jpg'
      im = Image.open(filename).convert('L')
      im.save(resaved_filename, 'JPEG', quality = quality)
      resaved_im = Image.open(resaved_filename)
      na_im = ImageChops.difference(im, resaved_im)
      extrema = na_im.getextrema()
      max_diff = max([ex for ex in extrema])
      if max_diff == 0:
         max_diff = 1      
      na_im = ImageEnhance.Brightness(na_im).enhance(intensity)
      return na_im

   def apply_na(self, file_path, sl=50):
      intensity=sl
      na=self.noise_analysis(file_path, 90, intensity)
      na.save(resaved_filename, 'JPEG')
      return na