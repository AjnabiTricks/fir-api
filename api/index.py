from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import re
import time

app = Flask(__name__)
CORS(app)

# ============================================
# CNIC HELPER FUNCTIONS
# ============================================

def normalize_cnic(cnic):
    digits = re.sub(r'\D', '', cnic)
    if len(digits) == 13:
        return f"{digits[:5]}-{digits[5:12]}-{digits[12]}"
    return cnic

def validate_cnic(cnic):
    digits = re.sub(r'\D', '', cnic)
    return len(digits) == 13 and digits.isdigit()

# ============================================
# REAL API SEARCH WITH RETRY
# ============================================

def search_cnic(cnic):
    """Real API call with multiple attempts"""
    
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
    
    # 🔥 3 attempts with different timeouts
    timeouts = [10, 15, 20]
    
    for attempt, timeout in enumerate(timeouts):
        try:
            print(f"Attempt {attempt + 1} for CNIC: {cnic} (timeout: {timeout}s)")
            
            response = requests.post(
                url, 
                data=data, 
                headers=headers, 
                timeout=timeout
            )
            
            if response.status_code == 200:
                text = response.text
                if text.startswith('\ufeff'):
                    text = text[1:]
                
                result = json.loads(text)
                
                # Check if real data received
                if result and 'CRO' in result:
                    print(f"✅ Real data found for CNIC: {cnic}")
                    return {
                        "success": True,
                        "source": "real",
                        "data": result
                    }
                else:
                    print(f"⚠️ No CRO data in response")
                    
        except requests.exceptions.Timeout:
            print(f"⏰ Attempt {attempt + 1} timed out")
            if attempt < 2:
                time.sleep(1)
            continue
            
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} error: {str(e)}")
            if attempt < 2:
                time.sleep(1)
            continue
    
    # All attempts failed
    print(f"❌ All attempts failed for CNIC: {cnic}")
    return {
        "success": False,
        "source": "error",
        "error": "API not responding"
    }

# ============================================
# FORMAT REAL DATA
# ============================================

def format_real_data(data, cnic):
    """Format real API data"""
    
    result = {
        "success": True,
        "cnic": cnic,
        "source": "real",
        "data": {}
    }
    
    if 'CRO' in data and 'cro' in data['CRO'] and 'basicInfo' in data['CRO']['cro']:
        info = data['CRO']['cro']['basicInfo']
        result["data"]["basic_info"] = {
            'name': info.get('sus_name', 'N/A'),
            'father_name': info.get('sus_parent_name', 'N/A'),
            'gender': info.get('sus_gender', 'N/A'),
            'caste': info.get('sus_cast', 'N/A'),
            'address': info.get('sus_address', 'N/A'),
            'phone': info.get('sus_phone', 'N/A'),
            'status': info.get('sus_status', 'N/A')
        }
        
        # Photo
        if 'photo' in info and info['photo']:
            result["data"]["photo"] = {
                'base64': info['photo'][:100] + '...'  # Truncated for display
            }
    
    # FIR Records
    if 'CRO' in data and 'cro' in data['CRO'] and 'firdetail' in data['CRO']['cro']:
        firs = data['CRO']['cro']['firdetail']
        result["data"]["fir_records"] = []
        for fir in firs:
            result["data"]["fir_records"].append({
                'district': fir.get('fir_district', 'N/A'),
                'police_station': fir.get('fir_ps', 'N/A'),
                'fir_number': fir.get('fir_no', 'N/A'),
                'year': fir.get('fir_year', 'N/A'),
                'section': fir.get('secName', 'N/A'),
                'offence_date': fir.get('fir_offence_date', 'N/A'),
                'offence': fir.get('fir_offecnce', 'N/A'),
                'status': fir.get('fir_status', 'N/A')
            })
    
    # Suspects
    if 'Mulzmaan' in data and data['Mulzmaan']:
        result["data"]["suspects"] = []
        for suspect in data['Mulzmaan']:
            result["data"]["suspects"].append({
                'name': suspect.get('sus_name', 'N/A'),
                'status': suspect.get('sus_status', 'N/A')
            })
    
    # Hotel Records
    if 'Hotel_travelEye' in data and 'arrHotel' in data['Hotel_travelEye']:
        result["data"]["hotel_records"] = []
        for hotel in data['Hotel_travelEye']['arrHotel']:
            result["data"]["hotel_records"].append({
                'hotel_name': hotel.get('HotelName', 'N/A'),
                'check_in': hotel.get('CheckIn', 'N/A'),
                'check_out': hotel.get('CheckOut', 'N/A')
            })
    
    # Summary
    result["data"]["summary"] = {
        'total_fir': len(result["data"].get('fir_records', [])),
        'total_suspects': len(result["data"].get('suspects', [])),
        'total_hotels': len(result["data"].get('hotel_records', [])),
        'has_photo': 'photo' in result["data"]
    }
    
    return result

# ============================================
# GENERATE DYNAMIC MOCK DATA (Different for each CNIC)
# ============================================

def get_dynamic_mock_data(cnic):
    """Generate unique mock data based on CNIC"""
    
    # Use CNIC to generate different data
    cnic_hash = sum(int(d) for d in re.sub(r'\D', '', cnic)) % 100
    
    names = ["Ali Khan", "Ahmed Raza", "Muhammad Usman", "Sajid Hussain", "Asif Mahmood"]
    cities = ["Lahore", "Karachi", "Islamabad", "Rawalpindi", "Faisalabad"]
    police_stations = ["Model Town", "Defence", "Gulberg", "Saddar", "Cantt"]
    offences = ["Theft", "Robbery", "Assault", "Fraud", "Drug Possession", "Murder"]
    statuses = ["Under Investigation", "Challan Filed", "Court Trial", "Disposed", "Acquitted"]
    
    # Deterministic selection based on CNIC
    name_idx = cnic_hash % len(names)
    city_idx = (cnic_hash + 5) % len(cities)
    ps_idx = (cnic_hash + 10) % len(police_stations)
    offence_idx = (cnic_hash + 15) % len(offences)
    status_idx = (cnic_hash + 20) % len(statuses)
    
    fir_number = f"{100 + cnic_hash}/2024"
    
    return {
        "success": True,
        "cnic": cnic,
        "source": "mock",
        "message": "Real API unavailable. Showing generated test data.",
        "data": {
            "basic_info": {
                "name": names[name_idx],
                "father_name": f"Father of {names[name_idx]}",
                "gender": "Male" if name_idx % 2 == 0 else "Female",
                "caste": "Awan",
                "address": f"{cities[city_idx]}, Punjab",
                "phone": f"03{str(cnic_hash).zfill(2)}-{str(cnic_hash*100).zfill(7)}",
                "status": "Active"
            },
            "fir_records": [
                {
                    "district": cities[city_idx],
                    "police_station": police_stations[ps_idx],
                    "fir_number": fir_number,
                    "year": "2024",
                    "section": f"Section {300 + cnic_hash % 100} PPC",
                    "offence_date": f"2024-{str((cnic_hash % 12)+1).zfill(2)}-{str((cnic_hash % 28)+1).zfill(2)}",
                    "offence": offences[offence_idx],
                    "status": statuses[status_idx]
                }
            ],
            "suspects": [
                {
                    "name": names[(name_idx + 1) % len(names)],
                    "status": statuses[(status_idx + 1) % len(statuses)]
                }
            ],
            "hotel_records": [
                {
                    "hotel_name": f"Hotel {cities[city_idx]}",
                    "check_in": f"2024-{str((cnic_hash % 12)+1).zfill(2)}-{str((cnic_hash % 28)+1).zfill(2)}",
                    "check_out": f"2024-{str((cnic_hash % 12)+1).zfill(2)}-{str((cnic_hash % 28)+3).zfill(2)}"
                }
            ],
            "summary": {
                "total_fir": 1,
                "total_suspects": 1,
                "total_hotels": 1,
                "has_photo": False
            }
        }
    }

# ============================================
# MAIN API ENDPOINT
# ============================================

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
    
    # 🔥 Try real API first
    print(f"🔍 Searching for CNIC: {normalized}")
    api_result = search_cnic(normalized)
    
    # If real API succeeded
    if api_result["success"] and api_result["source"] == "real":
        formatted = format_real_data(api_result["data"], normalized)
        return jsonify(formatted)
    
    # If real API failed, return dynamic mock data
    print(f"📊 Returning mock data for CNIC: {normalized}")
    mock_data = get_dynamic_mock_data(normalized)
    return jsonify(mock_data)

# ============================================
# ADDITIONAL ENDPOINTS
# ============================================

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "version": "2.0.0",
        "message": "API is working"
    })

@app.route('/api/test', methods=['GET'])
def test():
    """Test endpoint to check if API is working"""
    return jsonify({
        "success": True,
        "message": "API is working!",
        "timestamp": time.time()
    })

@app.route('/')
def home():
    return """
    <h1>✅ FIR API is Working!</h1>
    <p>Use: <code>/api/fir?cnic=12345-6789012-3</code></p>
    <p>Use: <code>/api/health</code></p>
    <p>Use: <code>/api/test</code></p>
    """

app = app

if __name__ == '__main__':
    app.run()
