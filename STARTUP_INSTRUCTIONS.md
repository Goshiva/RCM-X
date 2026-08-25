# How to Start the Insurance Risk Adjustment Tool

## ⚡ Quick Start (Choose One Method)

### Method 1: **Double-Click Startup Script** ✨ (EASIEST)

1. **In Windows File Explorer**, navigate to `c:\RCMX\`
2. **Double-click** `START_APP.bat`
3. A terminal window will open and start the Flask app
4. Open your browser to: **http://localhost:5000**

---

### Method 2: **Use PowerShell**

1. Open **PowerShell**
2. Navigate to the RCMX folder:
   ```powershell
   cd c:\RCMX
   ```
3. Run the startup script:
   ```powershell
   powershell -ExecutionPolicy Bypass -File START_APP.ps1
   ```
4. Open browser to: **http://localhost:5000**

---

### Method 3: **Manual Terminal Command**

1. Open **PowerShell** or **Command Prompt**
2. Run:
   ```bash
   cd c:\RCMX
   .\venv\Scripts\activate
   python app.py
   ```
3. Open browser to: **http://localhost:5000**

---

## 📖 What You Should See

After running the startup script, you should see:
```
* Running on http://127.0.0.1:5000
* Debug mode: on
```

This means the app is running successfully! ✅

---

## 🌐 Access the Web Application

Once the app is running, open your browser and go to:

### **http://localhost:5000**

You should see the Insurance Risk Adjustment Tool dashboard with:
- 💊 **Dashboard** - Statistics overview
- 📄 **Upload PDF** - Process medical documents
- 🧮 **Risk Calculator** - Calculate RAF scores
- 📋 **Audit Trail** - Compliance tracking
- 📚 **HCC Reference** - Browse HCC codes

---

## 🛑 Stop the Application

**In the terminal window**, press: **`CTRL + C`**

The app will stop gracefully.

---

## ❓ Troubleshooting

### **Port 5000 Already in Use**

If you see: `"Address already in use"`

**Solution:**
1. Edit the last line in `app.py`:
   ```python
   if __name__ == '__main__':
       app.run(debug=True, host='0.0.0.0', port=5001)  # Change 5000 to 5001
   ```
2. Run again and use: **http://localhost:5001**

---

### **Flask Module Not Found**

If you see: `ModuleNotFoundError: No module named 'flask'`

**Solution - Ensure you're using the virtual environment:**
```bash
cd c:\RCMX
.\venv\Scripts\activate
python -m pip install flask flask-cors
python app.py
```

---

### **Browser Can't Connect**

If you get: `"Connection refused"` or `"ERR_CONNECTION_REFUSED"`

1. Check the terminal - Flask should show: `Running on http://127.0.0.1:5000`
2. Wait 5 seconds for the server to fully start
3. Try different URL: `http://127.0.0.1:5000` or `http://10.251.11.122:5000`
4. Make sure you're using `localhost` not `192.168.x.x`

---

## 📝 Quick Tips

- **Keep the terminal window open** while using the app
- **Don't close the terminal** unless you want to stop the app
- **Use `http://localhost:5000`** (not `https://`)
- **First load may take a few seconds** (initializing modules)

---

## 🎯 What to Do Next

Once the app loads:

1. **Dashboard Tab** - View statistics
2. **Upload Tab** - Try uploading a PDF
3. **Risk Calculator Tab** - Calculate a patient's risk:
   - Patient ID: `PAT-001`
   - Age: `72`
   - Gender: `Male`
   - Insurance Model: `Medicare Advantage`
   - ICD-10 Codes: `E11.9, I50, J44.9`
   - Click "Calculate Risk"
4. **View Results** - RAF score, premiums, recommendations
5. **Export Report** - Download in PDF/Excel/JSON

---

## 🚀 You're All Set!

The Insurance Risk Adjustment Tool is ready to use!

If you need help, check:
- **README.md** - Full documentation
- **QUICKSTART.md** - Feature overview
- Source code comments in `/src/` modules

**Enjoy! 💼**
