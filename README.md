# 🛡️ AegisPix – Secure Image Encryption & Decryption

AegisPix is a web-based image encryption and secure sharing application built using Python and Flask. It allows users to send images securely through encryption and enables receivers to decrypt them using a secret key.

## 🚀 Live Demo

**Try AegisPix here:**

https://image-encryption-decryption-flask-app-1.onrender.com

*Note: The free demo may take some time to load after inactivity. Uploaded image files are currently stored locally and may disappear after a Render restart or redeployment.*

## ✨ Features

- User Registration and Login
- Secure Image Upload
- Image Encryption
- Image Decryption using a Secret Key
- Secret Key Verification
- Send Images to Registered Users
- Receiver Inbox
- Image History Tracking
- User Profile and Statistics

## 🛠️ Technologies Used

**Backend**
- Python
- Flask
- PostgreSQL (Neon)

**Image Processing**
- OpenCV
- NumPy
- Custom Image Encryption and Decryption Algorithms

**Frontend**
- HTML
- CSS
- Jinja2 Templates

**Deployment**
- Render
- Neon PostgreSQL

## ⚙️ Run Locally

### 1. Clone the repository

```bash
git clone https://github.com/mtmsr1726/Image-Encryption-Decryption-Flask-App.git
cd Image-Encryption-Decryption-Flask-App
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Set the following environment variables:

- `DATABASE_URL` – PostgreSQL connection string
- `SECRET_KEY` – Flask application secret key

### 4. Run the application

```bash
python app.py
```

Open your browser:

```text
http://127.0.0.1:5000
```

## 🔐 How It Works

1. A user registers and logs into AegisPix.
2. The sender selects an image and chooses a receiver.
3. The sender provides a secret key.
4. The application encrypts the image.
5. The encrypted image is sent to the receiver.
6. The receiver enters the correct secret key.
7. The application decrypts and displays the original image.

## 👨‍💻 Developer

**Jaswanth Reddy**

GitHub: https://github.com/mtmsr1726
