import os
import ctypes
try:
    from keras.models import load_model  # type: ignore
except Exception:
    load_model = None  # Fallback when Keras/TensorFlow is not installed
import numpy as np
from PIL import Image, ImageChops, ImageEnhance, ImageFilter
import PIL.ImageQt
import cv2 as cv
from matplotlib import pyplot as plt
from website.ImageForgeryDetection.NeuralNets import initClassifier, initSegmenter
from skimage import feature


# Color-image denoising
from skimage.restoration import (denoise_wavelet,estimate_sigma)
from skimage.util import random_noise
# from sklearn.metrics import peak_signal_noise_ratio
import skimage.io

resaved_filename = os.path.join(os.getcwd(), 'media', 'tempresaved.jpg')
# Default relative path to model under project root: IFAKE_WebApp/models/proposed_ela_50_casia_fidac.h5
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DEFAULT_MODEL_PATH = os.path.join(PROJECT_ROOT, 'models', 'proposed_ela_50_casia_fidac.h5')
DEFAULT_SEGMENTER_WEIGHTS = os.path.join(PROJECT_ROOT, 'models', 'segmenter_weights.h5')


class FID: 
   
   def prepare_image(self,fname):
    image_size = (128, 128)
    return  np.array(self.convert_to_ela_image(fname,90).resize(image_size)).flatten() / 255.0   #return ela_image as a numpy array

                 
   def predict_result(self,fname):
      # If ML stack or model path is unavailable, return safe default
      if load_model is None or not os.path.exists(DEFAULT_MODEL_PATH):
         return ('Authentic', '0.00')

      model = load_model(DEFAULT_MODEL_PATH)
      class_names = ['Forged', 'Authentic']  # classification outputs
      test_image = self.prepare_image(fname)
      test_image = test_image.reshape(-1, 128, 128, 3)
      y_pred = model.predict(test_image)
      print('y_pred====', y_pred)
      y_pred_class = int(round(y_pred[0][0]))

      prediction = class_names[y_pred_class]
      if y_pred <= 0.5:
         confidence = f'{(1-(y_pred[0][0])) * 100:0.2f}'
      else:
         confidence = f'{(y_pred[0][0]) * 100:0.2f}'
      return (prediction, confidence)
      #"""


      
   def genMask(self,file_path):
      segmenter=initSegmenter()
      if os.path.exists(DEFAULT_SEGMENTER_WEIGHTS):
         segmenter.load_weights(DEFAULT_SEGMENTER_WEIGHTS)
      else:
         raise FileNotFoundError('Missing segmenter_weights.h5 in models directory')
      testimg=self.convert_to_ela_image(file_path,90).resize((256,256))
      testimg=testimg.getchannel('B')
      test=np.array(testimg)/np.max(testimg)
      test=test.reshape(-1,256,256,1)
      mask=segmenter.predict(test)
      mask=mask.reshape(256,256)
      mask=(mask*255).astype('uint8')
      # plt.figure('Binary Mask')
      # plt.imshow(mask, cmap='gray')
      # plt.show()
      mask_im = Image.fromarray(mask)
      mask_im.save(resaved_filename, 'JPEG')
      return mask_im


   def convert_to_ela_image(self,path,quality):
      import urllib.parse
      # Decode URL-encoded path to handle spaces and special characters
      decoded_path = urllib.parse.unquote(path)
      print('-----------path--------------',decoded_path)
      original_image = Image.open(decoded_path).convert('RGB')

      #resaving input image at the desired quality
      resaved_file_name = resaved_filename  
      original_image.save(resaved_file_name,'JPEG',quality=quality)
      resaved_image = Image.open(resaved_file_name)

      #pixel difference between original and resaved image
      ela_image = ImageChops.difference(original_image,resaved_image)
      
      #scaling factors are calculated from pixel extremas
      extrema = ela_image.getextrema()
      max_difference = max([pix[1] for pix in extrema])
      if max_difference ==0:
         max_difference = 1
      scale = 255.0 / max_difference
      
      #enhancing elaimage to brighten the pixels
      ela_image = ImageEnhance.Brightness(ela_image).enhance(scale)
      #ela_image.save("ela_image.png")
      return ela_image


      
   def show_ela(self, file_path,sl=50):
      
      intensity=sl
      ela_im=self.convert_to_ela_image(file_path, 90)
      # plt.figure('Error Level analysis')
      # plt.imshow(ela_im)
      # plt.show()
      ela_im.save(resaved_filename, 'JPEG')

      return ela_im


   def detect_edges(self, path):
      import urllib.parse
      decoded_path = urllib.parse.unquote(path)
      image = Image.open(decoded_path)   
      image = image.convert("L") #Converting to greyscale
      image = image.filter(ImageFilter.FIND_EDGES)
      image = np.array(image.resize((256,256)))
      image = np.reshape(image, (256, 256))
      edge_im = Image.fromarray(image)
      # plt.figure('Edge Map')
      # plt.imshow(image, cmap='gray', aspect='equal')
      # plt.show()
      edge_im.save(resaved_filename, 'JPEG')
      return edge_im

   def luminance_gradient(self, path):
      import urllib.parse
      decoded_path = urllib.parse.unquote(path)
      resaved_filename_png = os.path.join(os.getcwd(), 'media', 'luminance_gradient.png')
      img = cv.imread(decoded_path, 0)
      sobelx = cv.Sobel(img,cv.CV_64F,1,0,ksize=15)
      # Normalize to 0-255 range for proper display
      sobelx_norm = np.uint8(np.absolute(sobelx))
      image = Image.fromarray(sobelx_norm).resize((600,600))
      # Save as PNG for better browser compatibility
      image.save(resaved_filename_png, 'PNG')
      return image

      # plt.figure('Luminance Gradient')
      # plt.imshow(np.array(image), cmap='gray', aspect='equal')
      # plt.show()

   def noise_analysis(self, path, quality, intensity):
      import urllib.parse
      filename = urllib.parse.unquote(path)
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

# def ela_denoise_img(path, quality):
#     #denoise
#     global resaved_filename
#     temp_filename = resaved_filename
    
#     image = Image.open(path).convert('RGB')
#     image.save(temp_filename, 'JPEG', quality = quality)
#     temp_image = Image.open(temp_filename)
    
#     img=skimage.img_as_float(image) #converting image as float


#     sigma_est=estimate_sigma(img,multichannel=True,average_sigmas=True)  #Noise estimation

#     # Denoising using Bayes
#     img_bayes=denoise_wavelet(img,method='BayesShrink',mode='soft',wavelet_levels=3,
#                           wavelet='coif5',multichannel=True,convert2ycbcr=True,rescale_sigma=True)


#     #Denoising using Visushrink
#     img_visushrink=denoise_wavelet(img,method='VisuShrink',mode='soft',sigma=sigma_est/3,wavelet_levels=5,
#     wavelet='coif5',multichannel=True,convert2ycbcr=True,rescale_sigma=True)
    
#     from keras.preprocessing.image import array_to_img
#     img_denoised=array_to_img(img_bayes)
    
#     #ela 
#     ela_image = ImageChops.difference(img_denoised, temp_image)
    
#     extrema = ela_image.getextrema()
#     max_diff = max([ex[1] for ex in extrema])
#     if max_diff == 0:
#         max_diff = 1
#     scale = 255.0 / max_diff
#     ela_image = ImageEnhance.Brightness(ela_image).enhance(scale)
#     return ela_image

# def GLCM(imgRGB, threshold=192):
#   imgYCbCr = imgRGB.convert('YCbCr')
#   imgYCbCr = np.array(imgYCbCr)
#   Cb = Scharr_Operator(imgYCbCr[:,:,1], threshold)
#   Cr = Scharr_Operator(imgYCbCr[:,:,2], threshold)
#   Cb_GLCM = feature.texture.greycomatrix(Cb, [1],
#                                          [0, np.pi / 4, np.pi / 2, 3 * np.pi / 4], 
#                                          levels=threshold)[:, :, 0, :]
#   Cr_GLCM = feature.texture.greycomatrix(Cr, [1],
#                                          [0, np.pi / 4, np.pi / 2, 3 * np.pi / 4], 
#                                          levels=threshold)[:, :, 0, :]
#   GLCM_feature = np.concatenate((Cb_GLCM,Cr_GLCM),axis=2)
#   return GLCM_feature

# def Scharr_Operator(imgYCbCr, threshold=192):
#     x = cv.Scharr(imgYCbCr, cv.CV_16S, 1, 0)
#     y = cv.Scharr(imgYCbCr, cv.CV_16S, 0, 1)
#     dst = cv.addWeighted(abs(x), 0.5, abs(y), 0.5, 0)
#     dst = np.clip(dst,0,threshold-1)
#     return dst 