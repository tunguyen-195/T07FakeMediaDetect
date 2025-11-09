# 🔐 Security Notice

## ⚠️ IMPORTANT - Before Deployment

### SECRET_KEY

**Current Status:** 
- The `SECRET_KEY` in `webapp/T07FakeMediaDetect/settings.py` is a **development key**
- **DO NOT use this key in production!**

**Action Required:**

1. **Generate a new SECRET_KEY:**
   ```bash
   python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
   ```

2. **Store in environment variable:**
   ```bash
   # Create .env file
   cp webapp/.env.example webapp/.env
   
   # Edit .env and add your new secret key
   SECRET_KEY=your-new-generated-secret-key-here
   ```

3. **Update settings.py to use environment variable:**
   ```python
   import os
   from dotenv import load_dotenv
   
   load_dotenv()
   
   SECRET_KEY = os.environ.get('SECRET_KEY', 'fallback-dev-key')
   ```

---

## 🔒 Other Security Considerations

### For Production:

1. **DEBUG Mode:**
   ```python
   DEBUG = False  # ALWAYS False in production
   ```

2. **ALLOWED_HOSTS:**
   ```python
   ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
   ```

3. **Database:**
   - Use PostgreSQL/MySQL instead of SQLite
   - Store credentials in environment variables

4. **HTTPS:**
   - Always use HTTPS in production
   - Set `SECURE_SSL_REDIRECT = True`
   - Set `SESSION_COOKIE_SECURE = True`
   - Set `CSRF_COOKIE_SECURE = True`

5. **Static Files:**
   ```bash
   python manage.py collectstatic
   ```
   Use nginx/Apache to serve static files

---

## 📝 Development vs Production

### Current Configuration (Development):
✅ DEBUG = True  
✅ SECRET_KEY hardcoded (dev only!)  
✅ SQLite database  
✅ Django dev server  
✅ All hosts allowed  

### Production Configuration:
❌ DEBUG = False  
✅ SECRET_KEY from environment  
✅ PostgreSQL/MySQL database  
✅ Gunicorn/uWSGI + nginx  
✅ Specific ALLOWED_HOSTS  
✅ HTTPS only  

---

## 🎯 Quick Security Checklist

Before deploying to production:

- [ ] Generate new SECRET_KEY
- [ ] Set DEBUG = False
- [ ] Configure ALLOWED_HOSTS
- [ ] Use production database (PostgreSQL/MySQL)
- [ ] Enable HTTPS
- [ ] Set secure cookie flags
- [ ] Configure static file serving
- [ ] Set up proper logging
- [ ] Review file upload limits
- [ ] Configure CORS if needed
- [ ] Set up monitoring/alerts

---

## 📚 Resources

- Django Security Checklist: https://docs.djangoproject.com/en/3.2/howto/deployment/checklist/
- Django Production Settings: https://docs.djangoproject.com/en/3.2/howto/deployment/
- OWASP Top 10: https://owasp.org/www-project-top-ten/

---

**Note:** This project is currently configured for **development/research purposes**. Proper security hardening is required before production deployment.

**Updated:** 2025-11-10
