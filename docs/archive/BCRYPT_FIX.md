# Bcrypt Password Length Fix

## Problem
The service was failing during startup when creating the first superuser because bcrypt has a maximum password length of 72 bytes. Passwords longer than this cause bcrypt to fail.

## Solution Implemented

### 1. Added `DISABLE_BOOTSTRAP_USERS` Environment Variable
- **Purpose**: Skip superuser creation entirely (recommended for API key-based services)
- **Default**: `false` (for backward compatibility)
- **Usage**: `export DISABLE_BOOTSTRAP_USERS=true`

### 2. Password Length Validation
- Added validation in `app/core/config.py` to check password length
- Clear error message if password exceeds 72 bytes
- Runtime check in `app/main.py` with graceful error handling

### 3. Updated Default Password
- Changed from `changethis123` to `changethis` (shorter, safer default)

## How to Use

### For Extraction Service (API Key Auth)
```bash
# Skip user creation entirely - RECOMMENDED
export DISABLE_BOOTSTRAP_USERS=true
export DATABASE_URL="sqlite:///./data/dev.db"
export API_KEY="your-api-key"
uvicorn app.main:app --reload
```

### If You Need User Auth
```bash
# Keep password under 72 bytes
export FIRST_SUPERUSER_EMAIL=admin@example.com
export FIRST_SUPERUSER_PASSWORD=shortpass  # Must be <= 72 bytes!
export DATABASE_URL="sqlite:///./data/dev.db"
uvicorn app.main:app --reload
```

## Files Changed
1. **app/core/config.py**
   - Added `DISABLE_BOOTSTRAP_USERS` setting
   - Added password length validator
   - Updated default password

2. **app/main.py**
   - Check `DISABLE_BOOTSTRAP_USERS` before creating superuser
   - Added password length validation with clear error
   - Graceful failure handling

3. **Documentation**
   - `.env` - Added new variable with comments
   - `.env.example` - Updated with new settings
   - `QUICKSTART_LOCAL.md` - Added to quick start commands
   - `TAKEOFF_SERVICE.md` - Added to all setup examples
   - Added troubleshooting section for bcrypt error

## Why This Matters
- **Bcrypt Limitation**: Bcrypt silently truncates passwords over 72 bytes, which can cause security issues
- **Service Focus**: This extraction service uses API keys, not user auth, so superuser creation is unnecessary
- **Better Defaults**: Clear error messages and safe defaults prevent confusion

## Migration Guide
If you have an existing deployment:
1. Add `DISABLE_BOOTSTRAP_USERS=true` to your environment
2. OR shorten your `FIRST_SUPERUSER_PASSWORD` to <= 72 bytes
3. Restart the service