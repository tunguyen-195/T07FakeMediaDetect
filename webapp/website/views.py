import datetime
from django.shortcuts import render, redirect, HttpResponseRedirect
import asyncio
from multiprocessing import Pool
import subprocess
import shutil

# streamlit is not required for the Django web UI
import sys
import os

# Suppress TensorFlow warnings (GPU not found warnings are normal when running on CPU)
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'  # 0=all, 1=info, 2=warning, 3=error only
def FID():
    # Lazily import heavy ML dependencies only when needed
    from website.ImageForgeryDetection.FakeImageDetector import FID as _FID
    return _FID()
##from website.videoForgeryDetection.videoFunctions import *
from django.core.files.storage import FileSystemStorage

# Defer heavy image forensics imports until needed
# import website.ImageForgeryDetection.double_jpeg_compression as djc  # ADD1
# import website.ImageForgeryDetection.noise_variance as nvar
# import website.ImageForgeryDetection.copy_move_cfa as cfa
# import website.ImageForgeryDetection.copy_move_sift as sift

from optparse import OptionParser
from json import dumps
from pdf2image import convert_from_path

def detect_video_forgery(*args, **kwargs):
    from website.VideoForgeryDetection.detect_video import detect_video_forgery as _detect
    return _detect(*args, **kwargs)
from PIL import Image
from PIL.ExifTags import TAGS

# Create your views here.

fileurl = ''
inputImageUrl = ''
result = {}
inputVideoUrl = ''
fileVideoUrl = ''
infoDict = {}
inputImage=''


def getMetaData(path):
    """Extract image metadata using PIL EXIF (hachoir optional)"""
    global infoDict
    infoDict = {}
    # Ensure path is decoded (spaces, special chars)
    try:
        import urllib.parse
        imgPath = urllib.parse.unquote(path)
    except Exception:
        imgPath = path
    
    try:
        # Try PIL EXIF first (more reliable)
        img = Image.open(imgPath)
        exifdata = getattr(img, '_getexif', lambda: None)()
        if exifdata:
            for tag_id, value in exifdata.items():
                tag = TAGS.get(tag_id, tag_id)
                infoDict[str(tag)] = str(value)
        else:
            infoDict['Info'] = 'No EXIF metadata found'
        
        # Add basic file info
        import os
        file_stat = os.stat(imgPath)
        infoDict['File Size'] = f'{file_stat.st_size / 1024:.2f} KB'
        infoDict['Image Size'] = f'{img.size[0]} x {img.size[1]}'
        infoDict['Image Mode'] = img.mode
        
    except Exception as e:
        infoDict['meta_error'] = str(e)
        
    # Optionally try hachoir if available
    exeProcess = "hachoir-metadata"
    if shutil.which(exeProcess):
        try:
            process = subprocess.Popen([exeProcess, imgPath],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       universal_newlines=True)
            for tag in process.stdout:
                line = tag.strip().split(':')
                if len(line) >= 2:
                    key = line[0].strip()
                    # Don't overwrite PIL data
                    if key not in infoDict:
                        infoDict[key] = line[-1].strip()
        except Exception as e:
            pass  # Ignore hachoir errors, PIL data is enough


def get_video_metadata(filename):
    """Extract video metadata using OpenCV (fallback if hachoir not available)"""
    properties = {}
    
    try:
        # Try using hachoir-metadata if available
        if shutil.which('hachoir-metadata'):
            result = subprocess.Popen(['hachoir-metadata', filename, '--raw', '--level=3'],
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            results = result.stdout.read().decode('utf-8').split('\r\n')

            for item in results:
                if item.startswith('- duration: '):
                    duration = item.lstrip('- duration: ')
                    if '.' in duration:
                        t = datetime.datetime.strptime(item.lstrip('- duration: '), '%H:%M:%S.%f')
                    else:
                        t = datetime.datetime.strptime(item.lstrip('- duration: '), '%H:%M:%S')
                    seconds = (t.microsecond / 1e6) + t.second + (t.minute * 60) + (t.hour * 3600)
                    properties['duration'] = round(seconds)

                if item.startswith('- width: '):
                    properties['width'] = int(item.lstrip('- width: '))

                if item.startswith('- height: '):
                    properties['height'] = int(item.lstrip('- height: '))
        else:
            # Fallback: Use OpenCV to get metadata
            import cv2
            cap = cv2.VideoCapture(filename)
            if cap.isOpened():
                properties['width'] = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                properties['height'] = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
                if fps > 0:
                    properties['duration'] = round(frame_count / fps)
                    properties['fps'] = round(fps, 2)
                cap.release()
            else:
                raise Exception("Cannot open video file")
                
    except Exception as e:
        print(f"[WARNING] Could not extract video metadata: {str(e)}")
        # Return empty dict, let caller handle it
        properties = {}
    
    return properties


def index(request):
    return render(request, "index.html")


def video(request):
    return render(request, "video.html")


def image(request):
    return render(request, "image.html")


def pdf(request):
    return render(request, "pdf.html")


#pdf2image for loop
def runPdf2image(request):
    global filePdfUrl, inputPdfUrl, fileurl, inputImageUrl
    
    if request.POST.get('run'):
        inputPdf = request.FILES['input_pdf'] if 'input_pdf' in request.FILES else None
        if not inputPdf:
            return render(request, "pdf.html", {
                'error': 'Vui lòng chọn tệp PDF để phân tích.'
            })
        
        try:
            fs = FileSystemStorage()
            file = fs.save(inputPdf.name, inputPdf)
            fileurl = fs.url(file)
            inputPdfUrl = '../media/' + inputPdf.name
            fileurl = os.path.join(os.getcwd(), 'media', inputPdf.name)
            # Try to auto-detect Poppler (pdfinfo) location on Windows
            def find_poppler_path():
                # 1) Respect explicit env override
                env_path = os.environ.get('POPPLER_PATH')
                if env_path and os.path.exists(env_path):
                    return env_path
                # 2) If in PATH
                pdfinfo_exe = shutil.which('pdfinfo')
                if pdfinfo_exe:
                    return os.path.dirname(pdfinfo_exe)
                # 3) Probe common locations
                candidates = []
                local_appdata = os.environ.get('LOCALAPPDATA', '')
                if local_appdata:
                    winget_root = os.path.join(local_appdata, 'Microsoft', 'WinGet', 'Packages')
                    if os.path.isdir(winget_root):
                        # Walk once and return first pdfinfo.exe found
                        for root, _dirs, files in os.walk(winget_root):
                            if 'pdfinfo.exe' in files:
                                return root
                # Chocolatey
                candidates.append(r"C:\\ProgramData\\chocolatey\\lib\\poppler\\tools")
                # Scoop
                candidates.append(os.path.expanduser(r"~\\scoop\\apps\\poppler\\current\\bin"))
                # Program Files
                candidates.append(r"C:\\Program Files\\poppler\\bin")
                candidates.append(r"C:\\Program Files (x86)\\poppler\\bin")
                for c in candidates:
                    if os.path.isdir(c) and os.path.exists(os.path.join(c, 'pdfinfo.exe')):
                        return c
                return None

            poppler_path = find_poppler_path()
            print(f"[DEBUG] Poppler path: {poppler_path}")
            print(f"[DEBUG] Converting PDF: {fileurl}")
            
            images = convert_from_path(fileurl, poppler_path=poppler_path) if poppler_path else convert_from_path(fileurl)
            print(f"[DEBUG] Converted {len(images)} pages from PDF")
            
            imageurl = []
            pdfImagesResults = []
            
            for i in range(len(images)):
                # Save pages as images in the pdf
                pageName = inputPdf.name.replace(".pdf", "").replace(".PDF", "") + '_page' + str(i) + '.jpg'
                page_save_path = os.path.join(os.getcwd(), 'media', pageName)
                images[i].save(page_save_path, 'JPEG')
                print(f"[DEBUG] Saved page {i}: {page_save_path}")
                
                # This list is used to generate table on pdf.html
                imageurl.append('../media/' + pageName)
                imagefileurl = os.path.join(os.getcwd(), 'media', pageName)
                
                # Analyze each page
                res = FID().predict_result(imagefileurl)
                result = {'type': res[0], 'confidence': res[1]}
                pdfImagesResults.append(result)
                print(f"[DEBUG] Page {i} result: {res[0]} ({res[1]}%)")
            
            res = zip(imageurl, pdfImagesResults)
            return render(request, "pdf.html", {
                'input_pdf': inputPdfUrl,
                'pdf_img': res
            })
            
        except Exception as e:
            print(f"[ERROR] PDF processing failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return render(request, "pdf.html", {
                'error': f'Lỗi xử lý PDF: {str(e)}'
            })

    if request.POST.get('passImage'):
        try:
            counter = request.POST.get('passImage')
            inputImageUrl = request.POST.get('image_url-' + counter)
            
            # Set up fileurl for forensic tools
            if inputImageUrl:
                # Convert relative URL to absolute file path
                filename = os.path.basename(inputImageUrl)
                fileurl = os.path.join(os.getcwd(), 'media', filename)
                inputImage = inputImageUrl
                
                print(f"[DEBUG] Passing PDF page to image analysis: {fileurl}")
                
                return render(request, "image.html", {
                    'input_image': inputImageUrl
                })
        except Exception as e:
            print(f"[ERROR] Failed to pass PDF page: {str(e)}")
            return render(request, "image.html", {
                'result': {
                    'type': 'Lỗi',
                    'confidence': '0.00',
                    'detail': f'Lỗi: {str(e)}'
                }
            })
    
    # Default return
    return render(request, "pdf.html", {})



def runAnalysis(request):
    global fileurl, inputImageUrl, result, infoDict,inputImage
    
    if request.POST.get('run'):
            inputImage=''
            if inputImageUrl=='' or 'input_image' in request.FILES:   
                inputImg = request.FILES['input_image'] if 'input_image' in request.FILES else None
                if inputImg:
                    fs = FileSystemStorage()
                    file = fs.save(inputImg.name, inputImg)
                    fileurl = os.path.join(os.getcwd(), 'media', inputImg.name)
                    inputImageUrl = '../media/' + inputImg.name
            elif inputImageUrl!='':
                #inputImageUrl = inputImageUrl
                fileurl = os.path.join(os.getcwd(), 'media', os.path.basename(inputImageUrl))
            # Validate file path before proceeding
            try:
                import urllib.parse
                decoded_path = urllib.parse.unquote(fileurl or '')
            except Exception:
                decoded_path = fileurl or ''

            if not decoded_path or not os.path.exists(decoded_path):
                result = {'type': 'Lỗi', 'confidence': '0.00', 'detail': 'Vui lòng tải ảnh hoặc chọn ảnh trước khi chạy.'}
                return render(request, "image.html",
                              {'result': result, 'input_image': inputImageUrl or '', 'metadata': infoDict.items()})

            getMetaData(decoded_path)
            print('fileurl---------------------------',fileurl)
            res = FID().predict_result(decoded_path)

            if res[0] == 'Authentic':
                result = {'type': res[0], 'confidence': res[1]}
                inputImage=inputImageUrl
                inputImageUrl=''

                return render(request, "image.html",
                              {'result': result, 'input_image': inputImage, 'metadata': infoDict.items()})

            elif res[0] == 'Forged':
                # cmd = OptionParser("usage: %prog image_file [options]")
                # cmd.add_option('', '--imauto', help='Automatically search identical regions. (default: %default)', default=1)
                # cmd.add_option('', '--imblev',help='Blur level for degrading image details. (default: %default)', default=8)
                # cmd.add_option('', '--impalred',help='Image palette reduction factor. (default: %default)', default=15)
                # cmd.add_option('', '--rgsim', help='Region similarity threshold. (default: %default)', default=5)
                # cmd.add_option('', '--rgsize',help='Region size threshold. (default: %default)', default=1.5)
                # cmd.add_option('', '--blsim', help='Block similarity threshold. (default: %default)',default=200)
                # cmd.add_option('', '--blcoldev', help='Block color deviation threshold. (default: %default)', default=0.2)
                # cmd.add_option('', '--blint', help='Block intersection threshold. (default: %default)', default=0.2)
                # opt, args = cmd.parse_args()
                # if not args:
                #     cmd.print_help()
                #     sys.exit()
                # im_str = args[0]

                # print('\nRunning double jpeg compression detection...\n')
                # double_compressed = djc.detect(fileurl)      # check type of forgery
                # if(double_compressed): compression= 'Double compressed'
                # else: compression= 'Single compressed'

                # print('\nRunning noise variance inconsistency detection...')
                # noise_forgery = nvar.detect(fileurl)

                # if(noise_forgery): noise_var=1
                # else: noise_var= 0

                # print('\nRunning CFA artifact detection...\n')
                # identical_regions_cfa = cfa.detect(fileurl, opt, args)
                # identical_regions = dumps(identical_regions_cfa)
                # print(identical_regions_cfa, 'identical regions detected')

                # res= FID().predict_result(fileurl) called above
                
                result = {'type': res[0], 'confidence': res[
                    1]}  # 'compression':compression, 'noise_var':noise_var, 'identical_regions': identical_regions}
                inputImage=inputImageUrl
                inputImageUrl=''
                return render(request, "image.html",
                              {'result': result, 'input_image': inputImage, 'metadata': infoDict.items()})


def runVideoAnalysis(request):
    # Use session instead of global variables (more reliable)
    
    if request.POST.get('run'):
        input_video = request.FILES['input_video'] if 'input_video' in request.FILES else None
        if input_video:
            try:
                fs = FileSystemStorage()
                file = fs.save(input_video.name, input_video)
                inputVideoUrl = '../media/' + input_video.name
                fileVideoUrl = os.path.join(os.getcwd(), 'media', input_video.name)
                
                # Store in session for persistence
                request.session['inputVideoUrl'] = inputVideoUrl
                request.session['fileVideoUrl'] = fileVideoUrl
                
                print(f"[DEBUG] Video uploaded: {fileVideoUrl}")
                print(f"[DEBUG] Stored in session")
                return render(request, "video.html", {'input_video': inputVideoUrl})
            except Exception as e:
                print(f"[ERROR] Video upload failed: {str(e)}")
                error_result = {
                    'result': 'Lỗi',
                    'f_frames': 0,
                    'detail': f'Lỗi tải video: {str(e)}'
                }
                return render(request, "video.html", {'result': error_result})

    if request.POST.get('detect'):
        print(f"[DEBUG] Detect button clicked!")
        
        # Retrieve from session
        fileVideoUrl = request.session.get('fileVideoUrl', '')
        inputVideoUrl = request.session.get('inputVideoUrl', '')
        
        print(f"[DEBUG] Retrieved from session:")
        print(f"[DEBUG]   fileVideoUrl: {fileVideoUrl}")
        print(f"[DEBUG]   inputVideoUrl: {inputVideoUrl}")
        
        # Validate video file exists
        if not fileVideoUrl or not os.path.exists(fileVideoUrl):
            print(f"[ERROR] Video file not found or not uploaded yet")
            error_result = {
                'result': 'Lỗi',
                'f_frames': 0,
                'detail': 'Vui lòng tải video trước khi phân tích.'
            }
            return render(request, "video.html", {
                'input_video': inputVideoUrl if inputVideoUrl else '',
                'result': error_result
            })
        
        try:
            print(f"[DEBUG] Starting video analysis...")
            print(f"[DEBUG] Video path: {fileVideoUrl}")
            
            # Get metadata
            properties = get_video_metadata(fileVideoUrl)
            print(f"[DEBUG] Metadata extracted: {properties}")
            
            # Detect forgery
            result = detect_video_forgery(fileVideoUrl)
            print(f"[DEBUG] Detection result: {result}")
            
            return render(request, "video.html", {
                'input_video': inputVideoUrl,
                'result': result,
                'metadata': properties.items() if properties else []
            })
        except Exception as e:
            print(f"[ERROR] Video analysis failed: {str(e)}")
            import traceback
            traceback.print_exc()
            error_result = {
                'result': 'Lỗi phân tích',
                'f_frames': 0,
                'detail': str(e)
            }
            return render(request, "video.html", {
                'input_video': inputVideoUrl if inputVideoUrl else '',
                'result': error_result
            })
    
    # Default return if no action
    print(f"[DEBUG] No action detected in POST")
    print(f"[DEBUG] POST data keys: {list(request.POST.keys())}")
    return render(request, "video.html", {})


def getImages(request):
    global fileurl, inputImageUrl, result, inputImage
    
    # Validate that an image has been uploaded
    if not fileurl or not os.path.exists(fileurl):
        error_result = {
            'type': 'Lỗi',
            'confidence': '0.00',
            'detail': 'Vui lòng tải ảnh và chạy phân tích trước khi sử dụng công cụ forensics.'
        }
        return render(request, "image.html", {
            'result': error_result,
            'input_image': inputImage or '',
            'metadata': infoDict.items()
        })
    
    # Add timestamp to prevent browser caching
    import time
    timestamp = str(int(time.time()))
    
    try:
        if request.POST.get('mask'):
            print(f"[DEBUG] Running genMask on: {fileurl}")
            FID().genMask(fileurl)
            outputImageUrl = f"../media/tempresaved.jpg?t={timestamp}"
            return render(request, "image.html", {
                'url': outputImageUrl,
                'input_image': inputImage,
                'result': result,
                'metadata': infoDict.items()
            })

        elif request.POST.get('ela'):
            print(f"[DEBUG] Running show_ela on: {fileurl}")
            FID().show_ela(fileurl)
            outputImageUrl = f"../media/tempresaved.jpg?t={timestamp}"
            return render(request, "image.html", {
                'url': outputImageUrl,
                'input_image': inputImage,
                'result': result,
                'metadata': infoDict.items()
            })

        elif request.POST.get('edge_map'):
            print(f"[DEBUG] Running detect_edges on: {fileurl}")
            FID().detect_edges(fileurl)
            outputImageUrl = f"../media/tempresaved.jpg?t={timestamp}"
            return render(request, "image.html", {
                'url': outputImageUrl,
                'input_image': inputImage,
                'result': result,
                'metadata': infoDict.items()
            })

        elif request.POST.get('lum_gradiend'):
            print(f"[DEBUG] Running luminance_gradient on: {fileurl}")
            FID().luminance_gradient(fileurl)
            outputImageUrl = f"../media/luminance_gradient.png?t={timestamp}"
            return render(request, "image.html", {
                'url': outputImageUrl,
                'input_image': inputImage,
                'result': result,
                'metadata': infoDict.items()
            })

        elif request.POST.get('na'):
            print(f"[DEBUG] Running apply_na on: {fileurl}")
            FID().apply_na(fileurl)
            outputImageUrl = f"../media/tempresaved.jpg?t={timestamp}"
            return render(request, "image.html", {
                'url': outputImageUrl,
                'input_image': inputImage,
                'result': result,
                'metadata': infoDict.items()
            })
            
        elif request.POST.get('copy_move_sift'):
            print(f"[DEBUG] Running copy_move_sift on: {fileurl}")
            try:
                # Lazy import to avoid loading unless requested
                import website.ImageForgeryDetection.copy_move_sift as sift
                cmsift = sift.CopyMoveSIFT(fileurl)
                res_to_use = result
            except Exception as e:
                # Surface a friendly error in the UI instead of crashing
                print(f"[ERROR] SIFT analysis failed: {str(e)}")
                res_to_use = {
                    'type': 'Phân tích SIFT lỗi',
                    'confidence': '0.00',
                    'detail': str(e)
                }
            outputImageUrl = f"../media/tempresaved.jpg?t={timestamp}"
            return render(request, "image.html", {
                'url': outputImageUrl,
                'input_image': inputImage,
                'result': res_to_use,
                'metadata': infoDict.items()
            })
    
    except Exception as e:
        print(f"[ERROR] Forensic tool error: {str(e)}")
        import traceback
        traceback.print_exc()
        error_result = {
            'type': 'Lỗi',
            'confidence': '0.00',
            'detail': f'Đã xảy ra lỗi khi xử lý: {str(e)}'
        }
        outputImageUrl = f"../media/tempresaved.jpg?t={timestamp}"
        return render(request, "image.html", {
            'url': outputImageUrl,
            'input_image': inputImage,
            'result': error_result,
            'metadata': infoDict.items()
        })
    
    # If no action matched, return current state
    return render(request, "image.html", {
        'input_image': inputImage,
        'result': result,
        'metadata': infoDict.items()
    })
