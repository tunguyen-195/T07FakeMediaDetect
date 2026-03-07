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


def safe_print(*args, **kwargs):
    sep = kwargs.pop("sep", " ")
    end = kwargs.pop("end", "\n")
    target_streams = []
    if "file" in kwargs:
        target_streams.append(kwargs.pop("file"))
    target_streams.extend(
        [
            sys.stdout,
            getattr(sys, "__stdout__", None),
            sys.stderr,
            getattr(sys, "__stderr__", None),
        ]
    )
    text = sep.join(str(arg) for arg in args)
    if end is not None:
        text += end
    for stream in target_streams:
        if stream is None:
            continue
        try:
            stream.write(text)
            stream.flush()
            return
        except Exception:
            continue

# Create your views here.

fileurl = ''
inputImageUrl = ''
result = {}
inputVideoUrl = ''
fileVideoUrl = ''
infoDict = {}
inputImage=''
WEB_SAFE_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}


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


def build_browser_preview_url(file_path, original_name=None):
    """Return a browser-safe media URL for previewing uploaded images."""
    ext = os.path.splitext(file_path)[1].lower()
    media_name = os.path.basename(file_path)

    if ext in WEB_SAFE_IMAGE_EXTENSIONS:
        return '../media/' + media_name

    preview_stem = os.path.splitext(original_name or media_name)[0]
    preview_name = f"{preview_stem}_preview.jpg"
    preview_path = os.path.join(os.getcwd(), 'media', preview_name)

    try:
        with Image.open(file_path) as img:
            img.convert('RGB').save(preview_path, 'JPEG', quality=92)
        return '../media/' + preview_name
    except Exception as e:
        safe_print(f"[WARNING] Failed to build browser preview for {file_path}: {e}")
        return '../media/' + media_name


def get_display_image_name(file_path='', preview_url=''):
    if file_path:
        return os.path.basename(file_path)
    if preview_url:
        return os.path.basename(preview_url)
    return ''


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
        safe_print(f"[WARNING] Could not extract video metadata: {str(e)}")
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


def to_friendly_image_label(result_label, leaning_label=None):
    if result_label == 'Authentic':
        return '\u1ea2nh nguy\u00ean b\u1ea3n'
    if result_label == 'Forged':
        return '\u1ea2nh \u0111\u00e3 qua ch\u1ec9nh s\u1eeda'
    if result_label == 'Review':
        if leaning_label == 'Authentic':
            return 'Nghi ng\u1edd - nghi\u00eang v\u1ec1 \u1ea3nh nguy\u00ean b\u1ea3n'
        if leaning_label == 'Forged':
            return 'Nghi ng\u1edd - nghi\u00eang v\u1ec1 \u1ea3nh \u0111\u00e3 qua ch\u1ec9nh s\u1eeda'
        return 'Nghi ng\u1edd - c\u1ea7n ki\u1ec3m tra th\u00eam'
    return result_label


def build_review_detail(result_label, leaning_label=None, leaning_confidence=None):
    if result_label != 'Review':
        return ''

    if leaning_label == 'Authentic':
        return (
            'H\u1ec7 th\u1ed1ng ch\u01b0a \u0111\u1ee7 ch\u1eafc ch\u1eafn \u0111\u1ec3 k\u1ebft lu\u1eadn, '
            f'nh\u01b0ng hi\u1ec7n \u0111ang nghi\u00eang v\u1ec1 \u1ea3nh nguy\u00ean b\u1ea3n ({leaning_confidence:.2f}%).'
            if leaning_confidence is not None else
            'H\u1ec7 th\u1ed1ng ch\u01b0a \u0111\u1ee7 ch\u1eafc ch\u1eafn \u0111\u1ec3 k\u1ebft lu\u1eadn, nh\u01b0ng hi\u1ec7n \u0111ang nghi\u00eang v\u1ec1 \u1ea3nh nguy\u00ean b\u1ea3n.'
        )
    if leaning_label == 'Forged':
        return (
            'H\u1ec7 th\u1ed1ng ch\u01b0a \u0111\u1ee7 ch\u1eafc ch\u1eafn \u0111\u1ec3 k\u1ebft lu\u1eadn, '
            f'nh\u01b0ng hi\u1ec7n \u0111ang nghi\u00eang v\u1ec1 \u1ea3nh \u0111\u00e3 qua ch\u1ec9nh s\u1eeda ({leaning_confidence:.2f}%).'
            if leaning_confidence is not None else
            'H\u1ec7 th\u1ed1ng ch\u01b0a \u0111\u1ee7 ch\u1eafc ch\u1eafn \u0111\u1ec3 k\u1ebft lu\u1eadn, nh\u01b0ng hi\u1ec7n \u0111ang nghi\u00eang v\u1ec1 \u1ea3nh \u0111\u00e3 qua ch\u1ec9nh s\u1eeda.'
        )
    return '\u1ea2nh n\u00e0y c\u1ea7n ki\u1ec3m tra th\u00eam do hai detector ch\u01b0a \u0111\u1ed3ng thu\u1eadn ho\u00e0n to\u00e0n.'


#pdf2image for loop
def runPdf2image(request):
    global filePdfUrl, inputPdfUrl, fileurl, inputImageUrl
    
    if request.POST.get('run'):
        inputPdf = request.FILES['input_pdf'] if 'input_pdf' in request.FILES else None
        if not inputPdf:
            return render(request, "pdf.html", {
                'error': 'Vui lÃ²ng chá»n tá»‡p PDF Ä‘á»ƒ phÃ¢n tÃ­ch.'
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
                # 3) Check project-local poppler (bundled)
                project_poppler = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'poppler', 'Library', 'bin')
                if os.path.isdir(project_poppler) and os.path.exists(os.path.join(project_poppler, 'pdfinfo.exe')):
                    return project_poppler
                # 4) Probe common locations
                candidates = []
                local_appdata = os.environ.get('LOCALAPPDATA', '')
                if local_appdata:
                    winget_root = os.path.join(local_appdata, 'Microsoft', 'WinGet', 'Packages')
                    if os.path.isdir(winget_root):
                        for root, _dirs, files in os.walk(winget_root):
                            if 'pdfinfo.exe' in files:
                                return root
                # Chocolatey
                candidates.append(r"C:\ProgramData\chocolatey\lib\poppler\tools")
                # Scoop
                candidates.append(os.path.expanduser(r"~\scoop\apps\poppler\current\bin"))
                # Program Files
                candidates.append(r"C:\Program Files\poppler\bin")
                candidates.append(r"C:\Program Files (x86)\poppler\bin")
                # Common manual install locations
                candidates.append(r"C:\poppler\Library\bin")
                candidates.append(r"C:\poppler\bin")
                for c in candidates:
                    if os.path.isdir(c) and os.path.exists(os.path.join(c, 'pdfinfo.exe')):
                        return c
                return None

            poppler_path = find_poppler_path()
            safe_print(f"[DEBUG] Poppler path: {poppler_path}")
            safe_print(f"[DEBUG] Converting PDF: {fileurl}")
            
            images = convert_from_path(fileurl, poppler_path=poppler_path) if poppler_path else convert_from_path(fileurl)
            safe_print(f"[DEBUG] Converted {len(images)} pages from PDF")
            
            final_pdf_results = []
            
            for i in range(len(images)):
                # Save pages as images in the pdf
                pageName = inputPdf.name.replace(".pdf", "").replace(".PDF", "") + '_page' + str(i) + '.jpg'
                page_save_path = os.path.join(os.getcwd(), 'media', pageName)
                images[i].save(page_save_path, 'JPEG')
                safe_print(f"[DEBUG] Saved page {i}: {page_save_path}")
                
                # Generate URL
                image_url = '../media/' + pageName
                imagefileurl = os.path.join(os.getcwd(), 'media', pageName)
                
                # Analyze each page
                res = FID().predict_result_structured(imagefileurl, source_type="pdf_page", require_hidden=True)
                friendly_type = to_friendly_image_label(res['final_label'], res.get('leaning_label'))
                result_data = {
                    'type': friendly_type,
                    'confidence': f"{res['final_confidence']:0.2f}",
                    'requires_review': res['requires_review'],
                    'final_label': res['final_label'],
                    'leaning_label': res.get('leaning_label'),
                    'leaning_confidence': f"{res.get('leaning_confidence', 0):0.2f}",
                    'detail': build_review_detail(
                        res['final_label'],
                        res.get('leaning_label'),
                        res.get('leaning_confidence'),
                    ),
                }
                
                safe_print(f"[DEBUG] Page {i} result: {res['final_label']} ({res['final_confidence']:.2f}%)")
                
                final_pdf_results.append((image_url, result_data))
            
            return render(request, "pdf.html", {
                'input_pdf': inputPdfUrl,
                'pdf_img': final_pdf_results
            })
            
        except Exception as e:
            safe_print(f"[ERROR] PDF processing failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return render(request, "pdf.html", {
                'error': f'Lá»—i xá»­ lÃ½ PDF: {str(e)}'
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
                
                safe_print(f"[DEBUG] Passing PDF page to image analysis: {fileurl}")
                
                return render(request, "image.html", {
                    'input_image': inputImageUrl,
                    'input_image_name': get_display_image_name(fileurl, inputImageUrl),
                })
        except Exception as e:
            safe_print(f"[ERROR] Failed to pass PDF page: {str(e)}")
            return render(request, "image.html", {
                'result': {
                    'type': 'Lá»—i',
                    'confidence': '0.00',
                    'detail': f'Lá»—i: {str(e)}'
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
                    inputImageUrl = build_browser_preview_url(fileurl, inputImg.name)
            elif inputImageUrl!='':
                # Keep the original uploaded file when a browser-safe preview URL is being shown.
                if not fileurl or not os.path.exists(fileurl):
                    fileurl = os.path.join(os.getcwd(), 'media', os.path.basename(inputImageUrl))
            # Validate file path before proceeding
            try:
                import urllib.parse
                decoded_path = urllib.parse.unquote(fileurl or '')
            except Exception:
                decoded_path = fileurl or ''

            if not decoded_path or not os.path.exists(decoded_path):
                result = {'type': 'Lá»—i', 'confidence': '0.00', 'detail': 'Vui lÃ²ng táº£i áº£nh hoáº·c chá»n áº£nh trÆ°á»›c khi cháº¡y.'}
                return render(request, "image.html",
                              {
                                  'result': result,
                                  'input_image': inputImageUrl or '',
                                  'input_image_name': get_display_image_name(fileurl, inputImageUrl or ''),
                                  'metadata': infoDict.items()
                              })

            getMetaData(decoded_path)
            safe_print('fileurl---------------------------',fileurl)
            try:
                res = FID().predict_result_structured(
                    decoded_path,
                    source_type="image",
                    require_hidden=True,
                )
            except Exception as e:
                safe_print(f"[ERROR] Image analysis failed: {str(e)}")
                return render(
                    request,
                    "image.html",
                    {
                        'error': (
                            "Hidden detector MUN is unavailable or returned an error. "
                            f"Details: {str(e)}"
                        ),
                        'input_image': inputImageUrl or inputImage or '',
                        'input_image_name': get_display_image_name(fileurl, inputImageUrl or inputImage or ''),
                        'metadata': infoDict.items(),
                    },
                )
            friendly_type = to_friendly_image_label(res['final_label'], res.get('leaning_label'))
            
            result = {
                'type': friendly_type,
                'confidence': f"{res['final_confidence']:0.2f}",
                'requires_review': res['requires_review'],
                'final_label': res['final_label'],
                'leaning_label': res.get('leaning_label'),
                'leaning_confidence': f"{res.get('leaning_confidence', 0):0.2f}",
                'detail': build_review_detail(
                    res['final_label'],
                    res.get('leaning_label'),
                    res.get('leaning_confidence'),
                ),
            }
            
            inputImage = inputImageUrl
            inputImageUrl = ''
            
            return render(request, "image.html",
                          {
                              'result': result,
                              'input_image': inputImage,
                              'input_image_name': get_display_image_name(fileurl, inputImage),
                              'metadata': infoDict.items()
                          })


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
                
                safe_print(f"[DEBUG] Video uploaded: {fileVideoUrl}")
                safe_print(f"[DEBUG] Stored in session")
                return render(request, "video.html", {'input_video': inputVideoUrl})
            except Exception as e:
                safe_print(f"[ERROR] Video upload failed: {str(e)}")
                error_result = {
                    'result': 'Lá»—i',
                    'f_frames': 0,
                    'detail': f'Lá»—i táº£i video: {str(e)}'
                }
                return render(request, "video.html", {'result': error_result})

    if request.POST.get('detect'):
        safe_print(f"[DEBUG] Detect button clicked!")
        
        # Retrieve from session
        fileVideoUrl = request.session.get('fileVideoUrl', '')
        inputVideoUrl = request.session.get('inputVideoUrl', '')
        
        safe_print(f"[DEBUG] Retrieved from session:")
        safe_print(f"[DEBUG]   fileVideoUrl: {fileVideoUrl}")
        safe_print(f"[DEBUG]   inputVideoUrl: {inputVideoUrl}")
        
        # Validate video file exists
        if not fileVideoUrl or not os.path.exists(fileVideoUrl):
            safe_print(f"[ERROR] Video file not found or not uploaded yet")
            error_result = {
                'result': 'Lá»—i',
                'f_frames': 0,
                'detail': 'Vui lÃ²ng táº£i video trÆ°á»›c khi phÃ¢n tÃ­ch.'
            }
            return render(request, "video.html", {
                'input_video': inputVideoUrl if inputVideoUrl else '',
                'result': error_result
            })
        
        try:
            safe_print(f"[DEBUG] Starting video analysis...")
            safe_print(f"[DEBUG] Video path: {fileVideoUrl}")
            
            # Get metadata
            properties = get_video_metadata(fileVideoUrl)
            safe_print(f"[DEBUG] Metadata extracted: {properties}")
            
            # Detect forgery
            result = detect_video_forgery(fileVideoUrl)
            
            # Map result to Vietnamese
            if result.get('result') == 'Authentic':
                result['result'] = 'Video nguyÃªn báº£n'
            elif result.get('result') == 'Forged':
                result['result'] = 'Video Ä‘Ã£ qua chá»‰nh sá»­a'
                
            safe_print(f"[DEBUG] Detection result: {result}")
            
            return render(request, "video.html", {
                'input_video': inputVideoUrl,
                'result': result,
                'metadata': properties.items() if properties else []
            })
        except Exception as e:
            safe_print(f"[ERROR] Video analysis failed: {str(e)}")
            import traceback
            traceback.print_exc()
            error_result = {
                'result': 'Lá»—i phÃ¢n tÃ­ch',
                'f_frames': 0,
                'detail': str(e)
            }
            return render(request, "video.html", {
                'input_video': inputVideoUrl if inputVideoUrl else '',
                'result': error_result
            })
    
    # Default return if no action
    safe_print(f"[DEBUG] No action detected in POST")
    safe_print(f"[DEBUG] POST data keys: {list(request.POST.keys())}")
    return render(request, "video.html", {})


def getImages(request):
    global fileurl, inputImageUrl, result, inputImage
    
    # Validate that an image has been uploaded
    if not fileurl or not os.path.exists(fileurl):
        error_result = {
            'type': 'Lá»—i',
            'confidence': '0.00',
            'detail': 'Vui lÃ²ng táº£i áº£nh vÃ  cháº¡y phÃ¢n tÃ­ch trÆ°á»›c khi sá»­ dá»¥ng cÃ´ng cá»¥ forensics.'
        }
        return render(request, "image.html", {
            'result': error_result,
            'input_image': inputImage or '',
            'input_image_name': get_display_image_name(fileurl, inputImage),
            'metadata': infoDict.items()
        })
    
    # Add timestamp to prevent browser caching
    import time
    timestamp = str(int(time.time()))
    
    try:
        if request.POST.get('mask'):
            safe_print(f"[DEBUG] Running genMask on: {fileurl}")
            FID().genMask(fileurl)
            outputImageUrl = f"../media/tempresaved.jpg?t={timestamp}"
            return render(request, "image.html", {
                'url': outputImageUrl,
                'input_image': inputImage,
                'input_image_name': get_display_image_name(fileurl, inputImage),
                'result': result,
                'metadata': infoDict.items()
            })

        elif request.POST.get('ela'):
            safe_print(f"[DEBUG] Running show_ela on: {fileurl}")
            FID().show_ela(fileurl)
            outputImageUrl = f"../media/tempresaved.jpg?t={timestamp}"
            return render(request, "image.html", {
                'url': outputImageUrl,
                'input_image': inputImage,
                'input_image_name': get_display_image_name(fileurl, inputImage),
                'result': result,
                'metadata': infoDict.items()
            })

        elif request.POST.get('edge_map'):
            safe_print(f"[DEBUG] Running detect_edges on: {fileurl}")
            FID().detect_edges(fileurl)
            outputImageUrl = f"../media/tempresaved.jpg?t={timestamp}"
            return render(request, "image.html", {
                'url': outputImageUrl,
                'input_image': inputImage,
                'input_image_name': get_display_image_name(fileurl, inputImage),
                'result': result,
                'metadata': infoDict.items()
            })

        elif request.POST.get('lum_gradiend'):
            safe_print(f"[DEBUG] Running luminance_gradient on: {fileurl}")
            FID().luminance_gradient(fileurl)
            outputImageUrl = f"../media/luminance_gradient.png?t={timestamp}"
            return render(request, "image.html", {
                'url': outputImageUrl,
                'input_image': inputImage,
                'input_image_name': get_display_image_name(fileurl, inputImage),
                'result': result,
                'metadata': infoDict.items()
            })

        elif request.POST.get('na'):
            safe_print(f"[DEBUG] Running apply_na on: {fileurl}")
            FID().apply_na(fileurl)
            outputImageUrl = f"../media/tempresaved.jpg?t={timestamp}"
            return render(request, "image.html", {
                'url': outputImageUrl,
                'input_image': inputImage,
                'input_image_name': get_display_image_name(fileurl, inputImage),
                'result': result,
                'metadata': infoDict.items()
            })
            
        elif request.POST.get('copy_move_sift'):
            safe_print(f"[DEBUG] Running copy_move_sift on: {fileurl}")
            try:
                # Lazy import to avoid loading unless requested
                import website.ImageForgeryDetection.copy_move_sift as sift
                cmsift = sift.CopyMoveSIFT(fileurl)
                res_to_use = result
            except Exception as e:
                # Surface a friendly error in the UI instead of crashing
                safe_print(f"[ERROR] SIFT analysis failed: {str(e)}")
                res_to_use = {
                    'type': 'PhÃ¢n tÃ­ch SIFT lá»—i',
                    'confidence': '0.00',
                    'detail': str(e)
                }
            outputImageUrl = f"../media/tempresaved.jpg?t={timestamp}"
            return render(request, "image.html", {
                'url': outputImageUrl,
                'input_image': inputImage,
                'input_image_name': get_display_image_name(fileurl, inputImage),
                'result': res_to_use,
                'metadata': infoDict.items()
            })
    
    except Exception as e:
        safe_print(f"[ERROR] Forensic tool error: {str(e)}")
        import traceback
        traceback.print_exc()
        error_result = {
            'type': 'Lá»—i',
            'confidence': '0.00',
            'detail': f'ÄÃ£ xáº£y ra lá»—i khi xá»­ lÃ½: {str(e)}'
        }
        outputImageUrl = f"../media/tempresaved.jpg?t={timestamp}"
        return render(request, "image.html", {
            'url': outputImageUrl,
            'input_image': inputImage,
            'input_image_name': get_display_image_name(fileurl, inputImage),
            'result': error_result,
            'metadata': infoDict.items()
        })
    
    # If no action matched, return current state
    return render(request, "image.html", {
        'input_image': inputImage,
        'input_image_name': get_display_image_name(fileurl, inputImage),
        'result': result,
        'metadata': infoDict.items()
    })

