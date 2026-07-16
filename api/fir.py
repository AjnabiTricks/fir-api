from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json
import re
import time
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)

# ============================================
# CACHE SYSTEM (1 hour cache)
# ============================================

cache = {}
cache_time = {}

def get_cached_or_fetch(cnic):
    """Cache se data laayein agar available ho"""
    
    if cnic in cache:
        # Check if cache is still valid (1 hour)
        if datetime.now() - cache_time[cnic] < timedelta(hours=1):
            return cache[cnic]
    
    return None

def save_to_cache(cnic, data):
    """Data ko cache mein save karein"""
    cache[cnic] = data
    cache_time[cnic] = datetime.now()

# ============================================
# CNIC HELPER FUNCTIONS
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
# MOCK DATA (Jab real API down ho)
# ============================================

def get_mock_data(cnic):
    """Mock data for testing when real API is down"""
    
    return {
        "CRO": {
            "cro": {
                "basicInfo": {
                    "sus_name": "Test Person",
                    "sus_parent_name": "Test Father",
                    "sus_gender": "Male",
                    "sus_cast": "Awan",
                    "sus_address": "Lahore, Punjab",
                    "sus_phone": "0300-1234567",
                    "sus_status": "Active",
                    "photo": ""
                },
                "firdetail": [
                    {
                        "fir_district": "Lahore",
                        "fir_ps": "Model Town",
                        "fir_no": "123/2024",
                        "fir_year": "2024",
                        "secName": "Section 379 PPC",
                        "fir_offence_date": "2024-01-15",
                        "fir_offecnce": "Theft",
                        "fir_status": "Under Investigation"
                    },
                    {
                        "fir_district": "Lahore",
                        "fir_ps": "Defence",
                        "fir_no": "456/2023",
                        "fir_year": "2023",
                        "secName": "Section 324 PPC",
                        "fir_offence_date": "2023-12-20",
                        "fir_offecnce": "Attempt to Murder",
                        "fir_status": "Challan Filed"
                    }
                ]
            }
        },
        "Mulzmaan": [
            {
                "sus_name": "Test Suspect 1",
                "sus_parent_name": "Father Name",
                "sus_gender": "Male",
                "sus_cast": "Awan",
                "sus_address": "Lahore",
                "sus_phone": "0300-1234567",
                "sus_status": "Arrested"
            }
        ],
        "Jail": {
            "data": {
                "No_name": "Test Person",
                "No_cro_no": "CRO-12345",
                "No_district": "Lahore",
                "No_cro_district": "Lahore",
                "No_status": "Released"
            }
        },
        "Hotel_travelEye": {
            "arrHotel": [
                {
                    "guestName": "Test Guest",
                    "guestFatherName": "Father Name",
                    "CNIC": cnic,
                    "CheckIn": "2024-01-10",
                    "CheckOut": "2024-01-12",
                    "HotelName": "Test Hotel Lahore",
                    "HotelAddress": "Main Boulevard, Lahore",
                    "PoliceStation": "Model Town",
                    "District": "Lahore",
                    "type": "Hotel"
                }
            ],
            "arrTravel": [
                {
                    "Name": "Test Traveler",
                    "route_from": "Lahore",
                    "route_to": "Islamabad",
                    "datetime": "2024-01-08 10:00:00"
                }
            ]
        }
    }

# ============================================
# MAIN SEARCH FUNCTION
# ============================================

def search_cnic(cnic):
    """Punjab Police API se data fetch karein with retry"""
    
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
    
    # Retry logic - 3 attempts
    for attempt in range(3):
        try:
            print(f"Attempt {attempt + 1} for CNIC: {cnic}")
            
            # 30 second timeout
            response = requests.post(
                url, 
                data=data, 
                headers=headers, 
                timeout=30
            )
            
            # Check response
            if response.status_code == 200:
                text = response.text
                if text.startswith('\ufeff'):
                    text = text[1:]
                
                result = json.loads(text)
                
                # Check if valid data
                if result and 'CRO' in result:
                    return result
                else:
                    print(f"Attempt {attempt + 1}: No CRO data found")
                    
            else:
                print(f"Attempt {attempt + 1}: Status code {response.status_code}")
                
        except requests.exceptions.Timeout:
            print(f"Attempt {attempt + 1}: Timeout")
            if attempt < 2:  # Don't wait after last attempt
                time.sleep(2)  # Wait 2 seconds before retry
            continue
            
        except requests.exceptions.ConnectionError:
            print(f"Attempt {attempt + 1}: Connection Error")
            if attempt < 2:
                time.sleep(3)
            continue
            
        except Exception as e:
            print(f"Attempt {attempt + 1}: Error - {str(e)}")
            if attempt < 2:
                time.sleep(2)
            continue
    
    # All attempts failed
    return {"error": "API is not responding. Please try again later."}

# ============================================
# FORMAT COMPLETE RESPONSE
# ============================================

def format_complete_response(data, cnic):
    """Complete formatted response with all records"""
    
    if not data or "error" in data:
        return {
            "success": False,
            "cnic": cnic,
            "message": data.get("error", "No record found") if data else "No data"
        }
    
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
    
    # Basic Info
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
        
        # Photo
        if 'photo' in info and info['photo']:
            result['records']['photo'] = {
                'base64': info['photo'],
                'data_url': f"data:image/jpeg;base64,{info['photo']}"
            }
    
    # FIR Records
    if 'CRO' in data and 'cro' in data['CRO'] and 'firdetail' in data['CRO']['cro']:
        for fir in data['CRO']['cro']['firdetail']:
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
    
    # Suspects
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
    
    # Hotel Records
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
    
    # Travel Records
    if 'Hotel_travelEye' in data and 'arrTravel' in data['Hotel_travelEye']:
        for travel in data['Hotel_travelEye']['arrTravel']:
            result['records']['travel_records'].append({
                'name': travel.get('Name', 'N/A'),
                'route_from': travel.get('route_from', 'N/A'),
                'route_to': travel.get('route_to', 'N/A'),
                'datetime': travel.get('datetime', 'N/A')
            })
    
    # Jail Record
    if 'Jail' in data and 'data' in data['Jail']:
        jail = data['Jail']['data']
        result['records']['jail_record'] = {
            'name': jail.get('No_name', 'N/A'),
            'cro_no': jail.get('No_cro_no', 'N/A'),
            'district': jail.get('No_district', 'N/A'),
            'cro_district': jail.get('No_cro_district', 'N/A'),
            'status': jail.get('No_status', 'N/A')
        }
    
    # Summary
    result['records']['summary'] = {
        'total_fir': len(result['records']['fir_records']),
        'total_suspects': len(result['records']['suspects']),
        'total_hotels': len(result['records']['hotel_records']),
        'total_travels': len(result['records']['travel_records']),
        'has_photo': result['records']['photo'] is not None,
        'data_source': 'cache' if cnic in cache else 'live'
    }
    
    return result

# ============================================
# MAIN API ENDPOINT
# ============================================

@app.route('/api/fir', methods=['GET', 'POST'])
def get_fir():
    """Main API endpoint - GET or POST"""
    
    # Get CNIC
    if request.method == 'GET':
        cnic = request.args.get('cnic')
    else:
        cnic = request.json.get('cnic') if request.is_json else request.form.get('cnic')
    
    # Validate
    if not cnic:
        return jsonify({
            "success": False,
            "error": "CNIC required",
            "format": "GET: /api/fir?cnic=12345-6789012-3",
            "example": "/api/fir?cnic=61101-7980174-9"
        }), 400
    
    normalized = normalize_cnic(cnic)
    
    if not validate_cnic(normalized):
        return jsonify({
            "success": False,
            "error": "Invalid CNIC format",
            "format": "Use: 12345-6789012-3 or 1234567890123"
        }), 400
    
    # Check cache first
    cached_data = get_cached_or_fetch(normalized)
    if cached_data:
        return jsonify({
            "success": True,
            "cnic": normalized,
            "data": cached_data,
            "from_cache": True
        })
    
    # Try real API
    print(f"Searching for CNIC: {normalized}")
    result = search_cnic(normalized)
    
    # Agar error hai to mock data return karein
    if "error" in result:
        print("Using mock data (real API failed)")
        mock_data = get_mock_data(normalized)
        save_to_cache(normalized, mock_data)
        
        return jsonify({
            "success": True,
            "cnic": normalized,
            "data": mock_data,
            "from_cache": False,
            "source": "mock",
            "message": "Real API is not responding. Showing test data."
        })
    
    # Format and cache
    formatted_data = format_complete_response(result, normalized)
    save_to_cache(normalized, formatted_data)
    
    return jsonify(formatted_data)

# ============================================
# ADDITIONAL ENDPOINTS
# ============================================

@app.route('/api/fir/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "version": "2.0.0",
        "cache_size": len(cache),
        "features": ["all_records", "photos", "hotel", "travel", "jail", "fir", "mock_data"]
    })

@app.route('/api/fir/cache/clear', methods=['DELETE'])
def clear_cache():
    """Clear cache"""
    global cache, cache_time
    cache = {}
    cache_time = {}
    return jsonify({"success": True, "message": "Cache cleared"})

@app.route('/api/fir/validate', methods=['GET'])
def validate_cnic_only():
    """CNIC validation endpoint"""
    cnic = request.args.get('cnic')
    
    if not cnic:
        return jsonify({"error": "CNIC required"}), 400
    
    normalized = normalize_cnic(cnic)
    is_valid = validate_cnic(normalized)
    
    return jsonify({
        "cnic": cnic,
        "normalized": normalized,
        "valid": is_valid
    })

@app.route('/')
def home():
    return """
    <h1>🔍 FIR Tracking API v2.0</h1>
    <p>Complete CNIC tracking with all records + photos</p>
    
    <h3>📌 Endpoints:</h3>
    <ul>
        <li><code>GET /api/fir?cnic=12345-6789012-3</code> - Complete record</li>
        <li><code>GET /api/fir/health</code> - Health check</li>
        <li><code>GET /api/fir/validate?cnic=12345-6789012-3</code> - Validate CNIC</li>
        <li><code>DELETE /api/fir/cache/clear</code> - Clear cache</li>
    </ul>
    
    <h3>📊 Response Includes:</h3>
    <ul>
        <li>✅ Basic Info (Name, Father, Address, Phone)</li>
        <li>✅ Photo (Base64 format)</li>
        <li>✅ FIR Records (All)</li>
        <li>✅ Suspects (All)</li>
        <li>✅ Hotel Records (All)</li>
        <li>✅ Travel Records (All)</li>
        <li>✅ Jail Record</li>
        <li>✅ Summary</li>
    </ul>
    
    <h3>📱 Try it:</h3>
    <pre>
    /api/fir?cnic=61101-7980174-9
    </pre>
    """

# ============================================
# FOR VERCEL
# ============================================

app = app

if __name__ == '__main__':
    app.run(debug=True, port=5000)ess": False,
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
