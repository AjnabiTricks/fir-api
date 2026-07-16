from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import re
import base64
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ============================================
# CNIC Helper Functions
# ============================================

def normalize_cnic(cnic):
    """CNIC ko standard format mein convert karein"""
    digits = re.sub(r'\D', '', cnic)
    if len(digits) == 13:
        return f"{digits[:5]}-{digits[5:12]}-{digits[12]}"
    return cnic

def validate_cnic(cnic):
    """CNIC valid hai ya nahi check karein"""
    digits = re.sub(r'\D', '', cnic)
    return len(digits) == 13 and digits.isdigit()

# ============================================
# Main Search Function
# ============================================

def search_cnic(cnic):
    """Punjab Police API se complete data fetch karein"""
    url = "https://fir.punjabpolice.gov.pk/restapi/All_api/checkPersonForHrmis"
    
    headers = {
        'User-Agent': 'okhttp/4.9.1',
        'Content-Type': 'application/x-www-form-urlencoded',
        'PSRMS-API-KEY': 'POLICEPOMOBAPP3G4H5U6K8O8P57909V0C2FFD7F',
        'Connection': 'Keep-Alive',
        'Accept-Encoding': 'gzip'
    }
    
    data = {
        'user_id': '3858',
        'cnic': normalize_cnic(cnic),
        'group_id': '0',
        'region_id': '0',
        'district_id': ''
    }
    
    try:
        response = requests.post(url, data=data, headers=headers, timeout=15)
        
        # BOM character hatayein
        text = response.text
        if text.startswith('\ufeff'):
            text = text[1:]
        
        return json.loads(text)
        
    except Exception as e:
        return {"error": str(e)}

# ============================================
# Complete Response Formatter (All Records + Photo)
# ============================================

def format_complete_response(data, cnic):
    """Sab records aur photos ko format karein"""
    
    if not data or "error" in data:
        return {
            "success": False,
            "cnic": cnic,
            "message": data.get("error", "No record found")
        }
    
    # Main response structure
    result = {
        "success": True,
        "cnic": cnic,
        "timestamp": datetime.now().isoformat(),
        "records": {
            "basic_info": {},
            "photo": None,
            "fir_records": [],
            "suspects": [],
            "hotel_records": [],
            "travel_records": [],
            "jail_record": {},
            "summary": {}
        }
    }
    
    # ========== 1. BASIC INFO + PHOTO ==========
    if 'CRO' in data and 'cro' in data['CRO'] and 'basicInfo' in data['CRO']['cro']:
        info = data['CRO']['cro']['basicInfo']
        
        result['records']['basic_info'] = {
            'name': info.get('sus_name', 'N/A'),
            'father_name': info.get('sus_parent_name', 'N/A'),
            'gender': info.get('sus_gender', 'N/A'),
            'caste': info.get('sus_cast', 'N/A'),
            'address': info.get('sus_address', 'N/A'),
            'phone': info.get('sus_phone', 'N/A'),
            'status': info.get('sus_status', 'N/A')
        }
        
        # 🖼️ PHOTO - Base64 format mein
        if 'photo' in info and info['photo']:
            result['records']['photo'] = {
                'base64': info['photo'],
                'format': 'jpeg',
                'data_url': f"data:image/jpeg;base64,{info['photo']}"
            }
    
    # ========== 2. FIR RECORDS ==========
    if 'CRO' in data and 'cro' in data['CRO'] and 'firdetail' in data['CRO']['cro']:
        firs = data['CRO']['cro']['firdetail']
        for fir in firs:
            result['records']['fir_records'].append({
                'district': fir.get('fir_district', 'N/A'),
                'police_station': fir.get('fir_ps', 'N/A'),
                'fir_number': fir.get('fir_no', 'N/A'),
                'year': fir.get('fir_year', 'N/A'),
                'section': fir.get('secName', 'N/A'),
                'offence_date': fir.get('fir_offence_date', 'N/A'),
                'offence': fir.get('fir_offecnce', 'N/A'),
                'status': fir.get('fir_status', 'N/A')
            })
    
    # ========== 3. SUSPECTS (Mulzmaan) ==========
    if 'Mulzmaan' in data and data['Mulzmaan']:
        for suspect in data['Mulzmaan']:
            result['records']['suspects'].append({
                'name': suspect.get('sus_name', 'N/A'),
                'parent_name': suspect.get('sus_parent_name', 'N/A'),
                'gender': suspect.get('sus_gender', 'N/A'),
                'caste': suspect.get('sus_cast', 'N/A'),
                'address': suspect.get('sus_address', 'N/A'),
                'phone': suspect.get('sus_phone', 'N/A'),
                'status': suspect.get('sus_status', 'N/A')
            })
    
    # ========== 4. HOTEL RECORDS ==========
    if 'Hotel_travelEye' in data and 'arrHotel' in data['Hotel_travelEye']:
        for hotel in data['Hotel_travelEye']['arrHotel']:
            result['records']['hotel_records'].append({
                'guest_name': hotel.get('guestName', 'N/A'),
                'father_name': hotel.get('guestFatherName', 'N/A'),
                'cnic': hotel.get('CNIC', 'N/A'),
                'check_in': hotel.get('CheckIn', 'N/A'),
                'check_out': hotel.get('CheckOut', 'N/A'),
                'hotel_name': hotel.get('HotelName', 'N/A'),
                'hotel_address': hotel.get('HotelAddress', 'N/A'),
                'police_station': hotel.get('PoliceStation', 'N/A'),
                'district': hotel.get('District', 'N/A')
            })
    
    # ========== 5. TRAVEL RECORDS ==========
    if 'Hotel_travelEye' in data and 'arrTravel' in data['Hotel_travelEye']:
        for travel in data['Hotel_travelEye']['arrTravel']:
            result['records']['travel_records'].append({
                'name': travel.get('Name', 'N/A'),
                'route_from': travel.get('route_from', 'N/A'),
                'route_to': travel.get('route_to', 'N/A'),
                'datetime': travel.get('datetime', 'N/A')
            })
    
    # ========== 6. JAIL RECORD ==========
    if 'Jail' in data and 'data' in data['Jail']:
        jail = data['Jail']['data']
        result['records']['jail_record'] = {
            'name': jail.get('No_name', 'N/A'),
            'cro_no': jail.get('No_cro_no', 'N/A'),
            'district': jail.get('No_district', 'N/A'),
            'cro_district': jail.get('No_cro_district', 'N/A'),
            'status': jail.get('No_status', 'N/A')
        }
    
    # ========== 7. SUMMARY ==========
    result['records']['summary'] = {
        'total_fir': len(result['records']['fir_records']),
        'total_suspects': len(result['records']['suspects']),
        'total_hotels': len(result['records']['hotel_records']),
        'total_travels': len(result['records']['travel_records']),
        'has_photo': result['records']['photo'] is not None
    }
    
    return result

# ============================================
# API Endpoints
# ============================================

@app.route('/api/fir', methods=['GET', 'POST'])
def get_complete_record():
    """
    Complete record with photo
    GET: /api/fir?cnic=12345-6789012-3
    POST: /api/fir with JSON {"cnic": "12345-6789012-3"}
    """
    
    # Get CNIC
    if request.method == 'GET':
        cnic = request.args.get('cnic')
    else:
        cnic = request.json.get('cnic') if request.is_json else request.form.get('cnic')
    
    # Validation
    if not cnic:
        return jsonify({
            "success": False,
            "error": "CNIC required",
            "format": "Use: ?cnic=12345-6789012-3 or 1234567890123"
        }), 400
    
    normalized = normalize_cnic(cnic)
    
    if not validate_cnic(normalized):
        return jsonify({
            "success": False,
            "error": "Invalid CNIC format",
            "format": "Use: 12345-6789012-3 or 1234567890123"
        }), 400
    
    # Search
    raw_data = search_cnic(cnic)
    
    if "error" in raw_data:
        return jsonify({
            "success": False,
            "error": raw_data["error"]
        }), 500
    
    # Format complete response with all records + photo
    result = format_complete_response(raw_data, normalized)
    
    return jsonify(result)

@app.route('/api/fir/simple', methods=['GET'])
def get_simple_record():
    """Simple version with limited fields (faster)"""
    cnic = request.args.get('cnic')
    
    if not cnic:
        return jsonify({"error": "CNIC required"}), 400
    
    normalized = normalize_cnic(cnic)
    data = search_cnic(cnic)
    
    # Simple response
    simple = {
        "cnic": normalized,
        "name": "N/A",
        "fir_count": 0,
        "has_photo": False
    }
    
    if 'CRO' in data and 'cro' in data['CRO'] and 'basicInfo' in data['CRO']['cro']:
        info = data['CRO']['cro']['basicInfo']
        simple['name'] = info.get('sus_name', 'N/A')
        simple['has_photo'] = bool(info.get('photo'))
    
    if 'CRO' in data and 'cro' in data['CRO'] and 'firdetail' in data['CRO']['cro']:
        simple['fir_count'] = len(data['CRO']['cro']['firdetail'])
    
    return jsonify(simple)

@app.route('/api/fir/photo', methods=['GET'])
def get_photo_only():
    """Sirf photo return karein"""
    cnic = request.args.get('cnic')
    
    if not cnic:
        return jsonify({"error": "CNIC required"}), 400
    
    data = search_cnic(cnic)
    
    if 'CRO' in data and 'cro' in data['CRO'] and 'basicInfo' in data['CRO']['cro']:
        info = data['CRO']['cro']['basicInfo']
        if 'photo' in info and info['photo']:
            return jsonify({
                "success": True,
                "cnic": normalize_cnic(cnic),
                "photo": info['photo'],
                "data_url": f"data:image/jpeg;base64,{info['photo']}"
            })
    
    return jsonify({
        "success": False,
        "message": "Photo not found"
    }), 404

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "version": "2.0.0",
        "features": ["all_records", "photos", "hotel", "travel", "jail", "fir"]
    })

@app.route('/')
def home():
    return """
    <h1>🔍 Complete FIR Tracking API</h1>
    <p>All records + Photos in one response</p>
    
    <h3>📌 Endpoints:</h3>
    <ul>
        <li><code>GET /api/fir?cnic=12345-6789012-3</code> - Complete record with photo</li>
        <li><code>GET /api/fir/simple?cnic=12345-6789012-3</code> - Simple record (faster)</li>
        <li><code>GET /api/fir/photo?cnic=12345-6789012-3</code> - Only photo</li>
        <li><code>GET /api/health</code> - Health check</li>
    </ul>
    
    <h3>📊 Response Includes:</h3>
    <ul>
        <li>✅ Basic Info (Name, Father, Address, Phone)</li>
        <li>✅ 🖼️ Photo (Base64 format)</li>
        <li>✅ FIR Records (All)</li>
        <li>✅ Suspects (All)</li>
        <li>✅ Hotel Records (All)</li>
        <li>✅ Travel Records (All)</li>
        <li>✅ Jail Record</li>
        <li>✅ Summary</li>
    </ul>
    """

if __name__ == '__main__':
    app.run(debug=True, port=5000)
