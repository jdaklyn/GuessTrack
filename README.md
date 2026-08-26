# 🎵 GuessTrack

> A retro arcade-inspired, real-time multiplayer music guessing game built with Flask, Socket.IO, and the iTunes Search API.

---

## 🎮 Overview

**GuessTrack** delivers a nostalgic handheld console experience right in your browser. Test your music knowledge in single-player mode or challenge your friends in real-time **1v1 Duels**. Listen to progressive audio snippets, guess the track name letter-for-letter before time runs out, and climb the leaderboard!

---

## ✨ Key Features

* **⚔️ Real-Time 1v1 Multiplayer:** Seamless room creation and synchronization using WebSockets (Flask-SocketIO).
* **⏱️ Risk vs. Reward Audio Mechanics:** 
  * 1.5s preview $\rightarrow$ **+15 PTS**
  * 4.0s preview $\rightarrow$ **+10 PTS**
  * 8.0s preview $\rightarrow$ **+5 PTS**
* **🎧 Dynamic Music Catalog:** Real-time fetching of Turkish & Global tracks via the iTunes Search API with artist-term filtering.
* **🕹️ Retro Arcade Aesthetics:** CRT scanline overlays, reactive audio visualizers, tactile haptic feedback, and synthesized 8-bit sound effects powered by the Web Audio API.
* **🏆 Global & Solo Leaderboard:** Persistent high-score tracking powered by SQLite.

---

## 🛠️ Tech Stack

* **Backend:** Python, Flask, Flask-SocketIO, Eventlet, Gunicorn, SQLite3
* **Frontend:** Vanilla JavaScript (ES6+), HTML5, CSS3 (Mobile-First / Pixel-Art)
* **APIs & Protocols:** iTunes Search API, Web Audio API, WebSockets, Haptic Feedback API

---

## 🚀 Getting Started

### Prerequisites
* Python 3.9+ installed on your machine.

### Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/YOUR_USERNAME/GuessTrack.git](https://github.com/YOUR_USERNAME/GuessTrack.git)
   cd GuessTrack