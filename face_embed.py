import os
import cv2
import faiss
import json
import numpy as np
import threading
from datetime import datetime
from insightface.app import FaceAnalysis
import shutil
from typing import List
# We need UploadFile here to understand the object
from fastapi import UploadFile




# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAISS_INDEX_FILE = os.path.join(BASE_DIR, "face_embeddings.index")
METADATA_FILE = os.path.join(BASE_DIR, "face_metadata.json")
TEMP_DIR = "temp_uploads" # We can manage temp files here
EMBEDDING_DIM = 512
os.makedirs(TEMP_DIR, exist_ok=True)
RECOGNITION_THRESHOLD = 1.1 


# --- Global Initialization (Done ONCE on startup) ---
try:
    print("Initializing InsightFace model...")
    face_app = FaceAnalysis(name="buffalo_s", providers=["CPUExecutionProvider"])
    face_app.prepare(ctx_id=-1, det_size=(640, 640))
    print("InsightFace model initialized successfully.")
except Exception as e:
    print(f"Error initializing InsightFace model: {e}")
    face_app = None

# Thread-Lock for safety
faiss_lock = threading.Lock()


# --- This is the NEW "manager" function ---
def process_registration_object(username: str, photos: List[UploadFile]) -> dict:
    """
    THIS FUNCTION DOES ALL THE WORK.
    It takes the object from FastAPI, loops through images,
    saves them, and creates embeddings for each one.
    """
    # print(f"Vector_store processing ID: {username}, Name: {name}")
    print(f"Processing {len(photos)} images...")

    results = []
    # --- This is your "for { 5 ... }" loop, now inside vector_store.py ---
    print("ready to foe loop..")
    for i, photo_path in enumerate(photos):
        print("for loop started..",photo_path)
        temp_path = photo_path  # already saved
        
        try:
            # Just verify the file exists
            if not os.path.exists(temp_path):
                raise FileNotFoundError(f"{temp_path} not found.")
        except Exception as e:
            print(f"Failed to verify file: {e}")
            results.append({"status": "error", "message": f"File issue: {e}", "image_index": i})
            continue

        # 2. Create embeddings for each saved image
        result = create_embedding_for_file(
            username=username,
            image_path=temp_path,
            image_index=i
        )
        results.append(result)
    print("results :", results)
    success_count = sum(1 for r in results if r["status"] == "success")
    print("embeddings stored..",success_count)
    return {
        "message": f"Processed {len(photos)} images. {success_count} succeeded.",
        "username": username,
        "results_per_image": results
    }


# This is now an "internal" function, hidden from main.py
def create_embedding_for_file(username: str, image_path: str, image_index: int) -> dict:
    """
    Reads ONE image, generates embedding, stores it in FAISS.
    """
    print("user.....................",username)
    print("IMAGEindex.....................",image_index)
    print("image_path.....................",image_path)
    if face_app is None:
        return {"status": "error", "message": "FaceAnalysis model is not initialized."}

    try:
        # 1. Read and Process Image
        img = cv2.imread(image_path)
        if img is None:
            return {"status": "error", "message": f"Could not read image from {image_path}"}
        
        faces = face_app.get(img)
        
        if not faces:
            return {"status": "error", "message": "No face detected in the provided image."}
        
        # 2. Generate and Normalize Embedding
        emb = faces[0].embedding.astype("float32")
        emb /= np.linalg.norm(emb)
        emb_to_add = np.array([emb])

        # 3. Acquire Lock to safely write to files
        with faiss_lock:
            if os.path.exists(FAISS_INDEX_FILE):
                index = faiss.read_index(FAISS_INDEX_FILE)
            else:
                index = faiss.IndexFlatL2(EMBEDDING_DIM)
            
            if os.path.exists(METADATA_FILE):
                with open(METADATA_FILE, "r") as f:
                    metadata = json.load(f)
                print(f"[DEBUG] Loaded metadata entries: {len(metadata)}")
            else:
                metadata = []

            # 4. Add to Index and Metadata
            new_faiss_id = index.ntotal
            index.add(emb_to_add)
            print(f"[DEBUG] Added new embedding. New FAISS total: {index.ntotal}")
            
            new_meta_entry = {
                "faiss_id": new_faiss_id,
                "username": username,
                "image_index": image_index,
                "timestamp": datetime.utcnow().isoformat()
            }
            metadata.append(new_meta_entry)
            
            # 5. Save changes back to disk
            faiss.write_index(index, FAISS_INDEX_FILE)
            with open(METADATA_FILE, "w") as f:
                json.dump(metadata, f, indent=2)

        return {
            "status": "success", 
            "message": "Embedding added",
            "faiss_id": new_faiss_id,
            "image_index": image_index
        }

    except Exception as e:
        print(f"Error in _create_embedding_for_file: {e}")
        return {"status": "error", "message": str(e), "image_index": image_index}
    finally:
        # 6. Clean up the temporary image file
        if os.path.exists(image_path):
            os.remove(image_path)


def recognize_faces_in_frame(frame: np.ndarray) -> list:
    """
    Detects and recognizes faces in a single video frame.

    Input:
        frame (numpy array): A single frame from cv2.read()
    
    Output:
        A list of dictionaries, one for each face found.
        e.g., [
            {"status": "match", "data": {...metadata...}, "box": [x,y,w,h]},
            {"status": "unknown", "box": [x,y,w,h]}
        ]
    """
    
    # 1. Check if files exist before trying to load
    with faiss_lock:
        if not os.path.exists(FAISS_INDEX_FILE) or not os.path.exists(METADATA_FILE):
            print("FAISS index or metadata not found. Please register faces first.")
            return []
        
        # Load the index and metadata safely
        try:
            index = faiss.read_index(FAISS_INDEX_FILE)
            with open(METADATA_FILE, "r") as f:
                metadata = json.load(f)
        except Exception as e:
            print(f"Error loading index/metadata: {e}")
            return []

    if index.ntotal == 0:
        print("Index is empty.")
        return []

    # 2. Get faces from the frame
    # We use face_app.get() because it's the SAME model used for registration
    # This is much more accurate than the separate Haar Cascade detector
    try:
        faces = face_app.get(frame)
    except Exception as e:
        print(f"Error during face detection: {e}")
        return []

    results = []
    for face in faces:
        # 3. Get embedding and normalize it (MUST match registration)
        emb = face.embedding.astype("float32")
        emb /= np.linalg.norm(emb)
        emb_to_search = np.array([emb])

        # 4. Search the FAISS index
        # D = distances, I = faiss_ids (which are the list indices)
        # We search for the k=1 closest match
        D, I = index.search(emb_to_search, 1)
        
        distance = D[0][0]
        faiss_id = I[0][0]
        
        # Get the bounding box
        box = face.bbox.astype(int)
        
        # 5. Check if the match is below our threshold
        if distance < RECOGNITION_THRESHOLD:
            # It's a match! Get the metadata.
            match_data = metadata[faiss_id]
            print(f"✅ Match Found: {match_data['name']} (ID: {match_data['employee_id']}), Distance: {distance}")
            results.append({
                "status": "match",
                "data": match_data,
                "box": box
            })
        else:
            # No match found, person is unknown
            print(f"⚠️ Unknown Face Detected. Distance: {distance}")
            results.append({
                "status": "unknown",
                "box": box
            })
            
    return results