from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import re

app = Flask(__name__)
CORS(app)

def normalize_cnic(cnic):
    digits = re.sub(r'\D', '', cnic)
    if len(digits) == 13:
        return f"{digits[:5]}-{digits[5:12]}-{digits[12]}"
    return cnic

def validate_cnic(cnic):
    digits = re.sub(r'\D', '', cnic)
    return len(digits) == 13 and digits.isdigit()

def search_cnic(cnic):
    url = "https://fir.punjabpolice.gov.pk/restapi/All_api/checkPersonForHrmis"
    
    headers = {
        'User-Agent': 'okhttp/4.9.1',
        'Content-Type': 'application/x-www-form-urlencoded',
        'PSRMS-API-KEY': 'POLICEPOMOBAPP3G4H5U6K8O8P57909V0C2FFD7F',
    }
    
    data = {
        'user_id': '3858',
        'cnic': normalize_cnic(cnic),
        'group_id': '0',
        'region_id': '0',
        'district_id': ''
    }
    
    try:
        response = requests.post(url, data=data, headers=headers, timeout=8)
        text = response.text
        if text.startswith('\ufeff'):
            text = text[1:]
        return json.loads(text)
    except Exception as e:
        return {"error": str(e)}

def get_mock_data(cnic):
    return {
        "success": True,
        "cnic": cnic,
        "source": "mock",
        "data": {
            "basic_info": {
                "name": "Test Person",
                "father_name": "Test Father",
                "gender": "Male",
                "address": "Lahore, Punjab",
                "phone": "0300-1234567"
            },
            "fir_records": [
                {
                    "fir_number": "123/2024",
                    "police_station": "Model Town",
                    "district": "Lahore",
                    "offence": "Theft",
                    "status": "Under Investigation"
                }
            ]
        }
    }

@app.route('/api/fir', methods=['GET'])
def get_fir():
    cnic = request.args.get('cnic')
    
    if not cnic:
        return jsonify({
            "success": False,
            "error": "CNIC required",
            "format": "Use: /api/fir?cnic=12345-6789012-3"
        }), 400
    
    normalized = normalize_cnic(cnic)
    
    if not validate_cnic(normalized):
        return jsonify({
            "success": False,
            "error": "Invalid CNIC format",
            "format": "Use: 12345-6789012-3 or 1234567890123"
        }), 400
    
    # Try real API
    result = search_cnic(cnic)
    
    if "error" in result:
        return jsonify({
            "success": True,
            "cnic": normalized,
            "data": get_mock_data(normalized),
            "source": "mock",
            "message": "Real API not available. Showing test data."
        })
    
    return jsonify({
        "success": True,
        "cnic": normalized,
        "data": result,
        "source": "real"
    })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "version": "1.0.0"
    })

@app.route('/')
def home():
    return """
    <h1>✅ FIR API is Working!</h1>
    <p>Use: <code>/api/fir?cnic=12345-6789012-3</code></p>
    <p>Use: <code>/api/health</code></p>
    """

app = app

if __name__ == '__main__':
    app.run()
