from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import re
import json
import os
from typing import Dict, List, Optional

class ChineseVietnameseTranslator:
    def __init__(self):
        # Configuration options
        self.options = {
            "Ngoac": False,   # Use brackets
            "Motnghia": True, # Use only first meaning
            "daucach": '/',   # Separator for multiple meanings
            "DichLieu": True  # Remove specific characters (的, 了, 着)
        }
        
        # Dictionaries
        self.dict_pa = {}    # Pinyin dictionary (ChinesePhienAmWords.txt)
        self.dict_vp = {}    # Vietphrase dictionary (vietphrase.txt)
        self.dict_names = {} # Names dictionary
        
        # For sorting
        self.dict_vp_keys = []
        self.dict_names_keys = []
        
        # Load dictionaries automatically from current directory
        self.load_default_dictionaries()
        
    def load_default_dictionaries(self):
        """Load default dictionaries from current directory"""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Fixed dictionary file paths
        pa_dict_path = os.path.join(current_dir, "ChinesePhienAmWords.txt")
        vp_dict_path = os.path.join(current_dir, "vietphrase.txt")
        names_dict_path = os.path.join(current_dir, "Names.txt")
        
        # Load dictionaries
        print(f"Loading dictionaries from {current_dir}")
        pa_success = self.load_dict_from_file(pa_dict_path, 'pa')
        vp_success = self.load_dict_from_file(vp_dict_path, 'vp')
        names_success = self.load_dict_from_file(names_dict_path, 'names')
        
        # Log results
        print(f"Dictionary loading results: PA={pa_success}, VP={vp_success}, Names={names_success}")
        
    def load_dict_from_file(self, file_path, dict_type):
        """Load dictionary from a file"""
        result = {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith(('//', '#', '=')):
                        continue
                    parts = line.split('=', 1)
                    if len(parts) != 2:
                        continue
                    key, value = parts[0], parts[1].strip()
                    result[key] = value
            
            if dict_type == 'vp':
                self.dict_vp = result
                # Sort keys by length (descending) then alphabetically
                self.dict_vp_keys = sorted(self.dict_vp.keys(), key=lambda x: (-len(x), x))
            elif dict_type == 'pa':
                self.dict_pa = result
            elif dict_type == 'names':
                self.dict_names = result
                self.dict_names_keys = sorted(self.dict_names.keys(), key=lambda x: (-len(x), x))
            
            print(f"Loaded {len(result)} entries for {dict_type} dictionary from {file_path}")
            return True
        except Exception as e:
            print(f"Error loading dictionary from {file_path}: {e}")
            return False
            
    def trans_pa(self, text):
        """Translate text using pinyin dictionary"""
        result = ""
        for c in text:
            if c in self.dict_pa:
                result += " " + self.dict_pa[c]
            else:
                result += c
        return result
    
    def trans_vp(self, text):
        """Translate text using vietphrase dictionary"""
        if not self.dict_vp or not self.dict_pa:
            return text
            
        result = ""
        
        # First replace names if available
        if self.dict_names and self.dict_names_keys:
            for name in self.dict_names_keys:
                text = text.replace(name, ' ' + self.dict_names[name])
        
        # Prepare variables
        max_length = len(self.dict_vp_keys[0]) if self.dict_vp_keys else 0
        dichlieu = ['的', '了', '着'] if self.options["DichLieu"] else []
        
        # Main translation loop
        i = 0
        while i < len(text):
            found_match = False
            
            # Try to match the longest phrases first
            for j in range(max_length, 0, -1):
                if i + j > len(text):
                    continue
                    
                substr = text[i:i+j]
                
                if substr in self.dict_vp:
                    vp = self.dict_vp[substr]
                    
                    # Process the translation according to options
                    if self.options["Motnghia"]:
                        vp = vp.split(self.options["daucach"])[0]
                    
                    if self.options["Ngoac"]:
                        vp = f"[{vp.strip()}]"
                        
                    result += ' ' + vp
                    i += j
                    found_match = True
                    break
            
            # If no match found, process single character
            if not found_match:
                if i < len(text):
                    char = text[i]
                    
                    # Skip special characters if configured
                    if char in dichlieu:
                        i += 1
                        continue
                        
                    # Use pinyin or original character
                    if char in self.dict_pa:
                        result += ' ' + self.dict_pa[char]
                    else:
                        result += char
                    
                    i += 1
                else:
                    # Avoid infinite loop
                    break
                
        # Clean up multiple spaces
        return re.sub(r' +', ' ', result).strip()
    
    def translate(self, text):
        """Main translation function"""
        return self.trans_vp(text)
    
    def set_option(self, name, value):
        """Set translation option"""
        if name in self.options:
            self.options[name] = value
            return True
        return False
    
    def get_options(self):
        """Get current options"""
        return self.options.copy()
    
    def get_dictionary_status(self):
        """Get status of loaded dictionaries"""
        return {
            "pa_dict": len(self.dict_pa),
            "vp_dict": len(self.dict_vp),
            "names_dict": len(self.dict_names)
        }

# FastAPI Models
class TranslationRequest(BaseModel):
    text: str
    options: Optional[Dict[str, bool]] = None

class TranslationResponse(BaseModel):
    translated_text: str
    options_used: Dict

class OptionsRequest(BaseModel):
    options: Dict[str, bool]

class OptionsResponse(BaseModel):
    options: Dict
    success: bool

# Initialize FastAPI app
app = FastAPI(
    title="Chinese-Vietnamese Translator API",
    description="API for translating Chinese text to Vietnamese using pinyin and vietphrase dictionaries",
    version="1.0.0"
)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize translator as a global instance
translator = ChineseVietnameseTranslator()

# API Routes
@app.get("/")
async def root():
    """Root endpoint showing API status and dictionary info"""
    dict_status = translator.get_dictionary_status()
    return {
        "message": "Chinese-Vietnamese Translator API is running",
        "dictionaries": {
            "pinyin_dictionary": f"{dict_status['pa_dict']} entries loaded",
            "vietphrase_dictionary": f"{dict_status['vp_dict']} entries loaded",
            "names_dictionary": f"{dict_status['names_dict']} entries loaded"
        }
    }

@app.post("/translate", response_model=TranslationResponse)
async def translate_text(request: TranslationRequest):
    """
    Translate Chinese text to Vietnamese
    
    - **text**: Chinese text to translate
    - **options**: Optional translation options
    """
    # Update options if provided
    if request.options:
        for key, value in request.options.items():
            translator.set_option(key, value)
    
    # Translate text
    try:
        translated_text = translator.translate(request.text)
        return {
            "translated_text": translated_text,
            "options_used": translator.get_options()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation error: {str(e)}")

@app.get("/translate", response_model=TranslationResponse)
async def translate_text_get(text: str = Query(..., description="Chinese text to translate")):
    """
    Translate Chinese text to Vietnamese using GET method
    
    - **text**: Chinese text to translate
    """
    try:
        translated_text = translator.translate(text)
        return {
            "translated_text": translated_text,
            "options_used": translator.get_options()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Translation error: {str(e)}")

@app.get("/options", response_model=OptionsResponse)
async def get_options():
    """Get current translation options"""
    return {
        "options": translator.get_options(),
        "success": True
    }

@app.post("/options", response_model=OptionsResponse)
async def set_options(request: OptionsRequest):
    """
    Set translation options
    
    - **options**: Dictionary of options to set
    """
    success = True
    for key, value in request.options.items():
        if not translator.set_option(key, value):
            success = False
    
    return {
        "options": translator.get_options(),
        "success": success
    }

@app.get("/status")
async def get_status():
    """Get status of loaded dictionaries and options"""
    dict_status = translator.get_dictionary_status()
    return {
        "dictionaries": {
            "pinyin_dictionary": f"{dict_status['pa_dict']} entries loaded",
            "vietphrase_dictionary": f"{dict_status['vp_dict']} entries loaded",
            "names_dictionary": f"{dict_status['names_dict']} entries loaded"
        },
        "options": translator.get_options()
    }
@app.get("/translate_a/single", response_model=list)
async def translate_for_apk_compatibility(
    q: str = Query(..., description="Chinese text to translate (Google-compatible)"),
    # Các tham số sau đây được app gửi lên nhưng API của bạn không dùng,
    # chúng ta khai báo để FastAPI nhận và bỏ qua chúng một cách hợp lệ.
    client: Optional[str] = None,
    sl: Optional[str] = None,
    tl: Optional[str] = None,
    dt: Optional[str] = None
):
    """
    Endpoint giả lập API của Google Translate để tương thích với app APK có sẵn.
    - Nhận tham số 'q'
    - Trả về cấu trúc JSON dạng [[["dịch", "gốc"]]]
    """
    try:
        # Dùng chính bộ dịch của bạn để dịch văn bản từ tham số 'q'
        translated_text = translator.translate(q)
        
        # Tạo cấu trúc response y hệt API của Google/moldich
        google_style_response = [
            [
                [
                    translated_text,
                    q  # Văn bản gốc
                ]
            ]
        ]
        
        return google_style_response
        
    except Exception as e:
        # Nếu có lỗi, trả về một cấu trúc hợp lệ nhưng rỗng để tránh crash app
        # Hoặc bạn có thể raise HTTPException như các hàm khác
        # return [[["Lỗi dịch", q]]]
        raise HTTPException(status_code=500, detail=f"Translation error: {str(e)}")
def main():
    """Run the FastAPI application with uvicorn"""
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

if __name__ == "__main__":
    # This is for running the app directly
    main()