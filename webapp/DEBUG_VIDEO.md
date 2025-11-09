# 🐛 Debug Video Analysis

## Vấn đề hiện tại

Khi click "Phát hiện Giả mạo", không có kết quả xuất hiện.

### Các bước đã thực hiện:
1. ✅ Upload video → OK (status 200)
2. ✅ Click "Phát hiện Giả mạo" → POST request sent
3. ❌ Không thấy debug logs
4. ❌ Không có kết quả hiển thị

---

## 🔍 Checklist Debug

### 1. Kiểm tra request đến đúng endpoint chưa?

**Form action trong template:**
```html
<form method="POST" action="runVideoAnalysis" enctype="multipart/form-data">
```

**Expected:** POST to `/runVideoAnalysis`

**Check logs:**
```
[10/Nov/2025 00:17:16] "POST /runVideoAnalysis HTTP/1.1" 200 7206
```

✅ Request đến đúng endpoint

---

### 2. Kiểm tra button name

**Template:**
```html
<button type="submit" name="detect" value="detect">
    🔍 Phát hiện Giả mạo
</button>
```

**View check:**
```python
if request.POST.get('detect'):
    print("[DEBUG] Detect button clicked!")
```

❓ **Cần xác nhận:** Log này có xuất hiện không?

---

### 3. Kiểm tra global variables

**Problem:** Global variables `fileVideoUrl` và `inputVideoUrl` có thể bị mất giữa requests

**Why?**
- Django development server có thể restart
- Worker processes khác nhau
- Global variables không persistent

**Debug:**
```python
print(f"[DEBUG] fileVideoUrl: {fileVideoUrl if 'fileVideoUrl' in globals() else 'NOT SET'}")
```

---

### 4. Possible Issues

#### Issue A: Global variable lost
```python
# Upload: fileVideoUrl = 'path/to/video.mp4'
# (request ends)
# 
# Detect click: fileVideoUrl = '' (LOST!)
```

#### Issue B: Form not submitting properly
- JavaScript errors?
- CSRF token missing?
- Network error?

#### Issue C: View returning early
- Exception caught silently?
- Logic error in if/else?

---

## ✅ Solutions

### Solution 1: Use session instead of global

**Replace global variables with session:**

```python
def runVideoAnalysis(request):
    # Don't use global
    # global inputVideoUrl, fileVideoUrl
    
    if request.POST.get('run'):
        input_video = request.FILES['input_video'] if 'input_video' in request.FILES else None
        if input_video:
            try:
                fs = FileSystemStorage()
                file = fs.save(input_video.name, input_video)
                
                # Store in session
                request.session['inputVideoUrl'] = '../media/' + input_video.name
                request.session['fileVideoUrl'] = os.path.join(os.getcwd(), 'media', input_video.name)
                
                print(f"[DEBUG] Video uploaded: {request.session['fileVideoUrl']}")
                return render(request, "video.html", {
                    'input_video': request.session['inputVideoUrl']
                })
            except Exception as e:
                # ...
    
    if request.POST.get('detect'):
        print("[DEBUG] Detect button clicked!")
        
        # Get from session
        fileVideoUrl = request.session.get('fileVideoUrl', '')
        inputVideoUrl = request.session.get('inputVideoUrl', '')
        
        print(f"[DEBUG] fileVideoUrl from session: {fileVideoUrl}")
        
        if not fileVideoUrl or not os.path.exists(fileVideoUrl):
            # ...
        
        try:
            print(f"[DEBUG] Analyzing video: {fileVideoUrl}")
            properties = get_video_metadata(fileVideoUrl)
            result = detect_video_forgery(fileVideoUrl)
            print(f"[DEBUG] Result: {result}")
            
            return render(request, "video.html", {
                'input_video': inputVideoUrl,
                'result': result,
                'metadata': properties.items() if properties else []
            })
```

---

### Solution 2: Pass filename via hidden input

**Template:**
```html
<form method="POST" action="runVideoAnalysis">
    {% csrf_token %}
    
    <!-- Hidden field to store video path -->
    <input type="hidden" name="video_path" value="{{ input_video }}">
    
    <button type="submit" name="detect" value="detect">
        🔍 Phát hiện Giả mạo
    </button>
</form>
```

**View:**
```python
if request.POST.get('detect'):
    # Get video path from form
    inputVideoUrl = request.POST.get('video_path', '')
    
    if inputVideoUrl:
        # Convert relative URL to absolute path
        filename = os.path.basename(inputVideoUrl.replace('../media/', ''))
        fileVideoUrl = os.path.join(os.getcwd(), 'media', filename)
        
        print(f"[DEBUG] Video path from form: {fileVideoUrl}")
        
        if os.path.exists(fileVideoUrl):
            # Analyze...
```

---

## 🧪 Test Steps

### Step 1: Add more debug logs

Already added:
```python
if request.POST.get('detect'):
    print(f"[DEBUG] Detect button clicked!")
    print(f"[DEBUG] fileVideoUrl: {fileVideoUrl}")
```

### Step 2: Check browser console

Open DevTools (F12) → Console tab

Look for:
- JavaScript errors
- Network tab: Check POST request details
- Response preview

### Step 3: Check Django logs

Look for:
```
[DEBUG] Detect button clicked!
[DEBUG] fileVideoUrl: ...
[DEBUG] Analyzing video: ...
```

If NOT present → View code not executing

---

## 📝 Next Actions

1. ✅ Added debug logs to views.py
2. ⏳ Restart server: `restart.bat`
3. ⏳ Test again and check logs
4. ⏳ If still no logs → Apply Solution 1 (session)

---

**Status:** Debugging in progress  
**Date:** 2025-11-10
