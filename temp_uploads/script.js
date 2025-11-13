const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const openCameraBtn = document.getElementById('openCameraBtn');
const captureBtn = document.getElementById('captureBtn');
const submitBtn = document.getElementById('submitBtn');
const previewContainer = document.getElementById('previewContainer');
const form = document.getElementById('registerForm');
const userTableBody = document.querySelector('#userTable tbody');

let capturedImages = [];
let stream = null;

// Replace with your API URLs
const API_POST_URL = 'https://example.com/api/register';
const API_GET_URL = 'https://example.com/api/users';

// Open the camera
openCameraBtn.addEventListener('click', async () => {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true });
    video.srcObject = stream;
    video.style.display = 'block';
    captureBtn.disabled = false;
    openCameraBtn.disabled = true;
  } catch (err) {
    console.error("Error accessing camera:", err);
    alert("Could not access webcam.");
  }
});

// Capture image
captureBtn.addEventListener('click', () => {
  if (capturedImages.length >= 4) return;

  const context = canvas.getContext('2d');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  context.drawImage(video, 0, 0, canvas.width, canvas.height);

  canvas.toBlob((blob) => {
    capturedImages.push(blob);
    renderPreviews();

    if (capturedImages.length === 4) {
      captureBtn.disabled = true;
      submitBtn.disabled = false;
      stopCamera();
    }
  }, 'image/jpeg');
});

// Stop the camera stream
function stopCamera() {
  if (stream) {
    const tracks = stream.getTracks();
    tracks.forEach(track => track.stop());
    stream = null;
    video.style.display = 'none';
    openCameraBtn.disabled = false;
  }
}

// Render preview thumbnails with remove buttons
function renderPreviews() {
  previewContainer.innerHTML = '';

  capturedImages.forEach((imgBlob, index) => {
    const wrapper = document.createElement('div');
    wrapper.className = 'image-wrapper';

    const img = document.createElement('img');
    img.src = URL.createObjectURL(imgBlob);

    const removeBtn = document.createElement('button');
    removeBtn.className = 'remove-btn';
    removeBtn.textContent = '❌';
    removeBtn.addEventListener('click', () => {
      capturedImages.splice(index, 1);
      renderPreviews();
      captureBtn.disabled = capturedImages.length >= 4;
      submitBtn.disabled = capturedImages.length !== 4;
    });

    wrapper.appendChild(img);
    wrapper.appendChild(removeBtn);
    previewContainer.appendChild(wrapper);
  });
}

// Submit form
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = document.getElementById('username').value.trim();

  if (!username) {
    alert("Please enter a username.");
    return;
  }
  

  const formData = new FormData();
  formData.append('username', username);

  // ✅ Append each captured image individually
  capturedImages.forEach((img, i) => {
    formData.append('photos', img, `photo${i + 1}.jpg`);
  });

  try {
    const response = await fetch("http://127.0.0.1:8000/register_user", {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }

    
    if (response.ok) {
      alert('User registered successfully!');
      form.reset();
      previewContainer.innerHTML = '';
      capturedImages = [];
      captureBtn.disabled = true;
      submitBtn.disabled = true;
      openCameraBtn.disabled = false;
      loadUserTable();
    } else {
      console.log(response)
      alert('Failed to register user.');
    }
  } catch (error) {
    console.error('Error:', error);
    alert('Error submitting form.');
  }
});

// Fetch and display users
async function loadUserTable() {
  try {
    const response = await fetch(API_GET_URL);
    const users = await response.json();
    userTableBody.innerHTML = '';

    users.forEach(user => {
      const row = document.createElement('tr');
      const nameCell = document.createElement('td');
      nameCell.textContent = user.username;

      const imgCell = document.createElement('td');
      user.images.forEach(imgUrl => {
        const img = document.createElement('img');
        img.src = imgUrl;
        img.width = 50;
        img.style.marginRight = '5px';
        imgCell.appendChild(img);
      });

      row.appendChild(nameCell);
      row.appendChild(imgCell);
      userTableBody.appendChild(row);
    });
  } catch (error) {
    console.error('Error fetching users:', error);
  }
}

// Initial load
loadUserTable();
