document.addEventListener("DOMContentLoaded", function () {
    const navItems = document.querySelectorAll('.sidebar-nav li[data-section]');
    const sections = document.querySelectorAll('.content-section');
    const sidebar = document.getElementById('sidebar');
    let stream = null;

    // Toggle sidebar for mobile
    if (window.innerWidth < 992) {
        sidebar.classList.add('offcanvas', 'offcanvas-start');
        const toggleBtn = document.querySelector('.toggle-btn');
        toggleBtn.addEventListener('click', () => {
            sidebar.classList.add('show');
        });
        const closeBtn = document.getElementById('close-btn');
        closeBtn.classList.remove('d-none');
        closeBtn.addEventListener('click', () => {
            sidebar.classList.remove('show');
        });
    }

    // Navigation
    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const sectionId = item.getAttribute('data-section');
            if (sectionId) {
                navItems.forEach(i => {
                    i.classList.remove('active');
                    i.querySelector('a').classList.remove('active');
                });
                item.classList.add('active');
                item.querySelector('a').classList.add('active');
                sections.forEach(section => section.classList.remove('active'));
                document.getElementById(sectionId).classList.add('active');
                if (window.innerWidth < 992) {
                    sidebar.classList.remove('show');
                }
            }
        });
    });

    // Profile Edit
    const editProfileBtn = document.getElementById('edit-profile-btn');
    const saveProfileBtn = document.getElementById('save-profile-btn');
    const emailInput = document.getElementById('email');
    const positionInput = document.getElementById('position');
    const newFaceImageInput = document.getElementById('new-face-image');
    const profilePic = document.getElementById('profile-pic');
    const emailDisplay = document.getElementById('email-display');

    if (editProfileBtn) {
        editProfileBtn.addEventListener('click', () => {
            emailInput.classList.add('active');
            positionInput.classList.add('active');
            newFaceImageInput.style.display = 'block';
            emailDisplay.style.display = 'none';
            editProfileBtn.style.display = 'none';
            saveProfileBtn.style.display = 'block';
        });
    }

    if (newFaceImageInput) {
        newFaceImageInput.addEventListener('change', (event) => {
            const file = event.target.files[0];
            if (file) {
                profilePic.src = URL.createObjectURL(file);
            }
        });
    }

    if (saveProfileBtn) {
        saveProfileBtn.addEventListener('click', () => {
            const formData = new FormData();
            formData.append('email', emailInput.value);
            formData.append('position', positionInput.value);
            if (newFaceImageInput.files[0]) {
                formData.append('face_image', newFaceImageInput.files[0]);
            }
            fetch('/update_profile', { method: 'POST', body: formData })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Profile updated successfully!');
                        emailDisplay.textContent = emailInput.value;
                        emailInput.classList.remove('active');
                        positionInput.classList.remove('active');
                        newFaceImageInput.style.display = 'none';
                        emailDisplay.style.display = 'inline';
                        editProfileBtn.style.display = 'block';
                        saveProfileBtn.style.display = 'none';
                        location.reload();
                    } else {
                        alert(data.message);
                    }
                })
                .catch(error => console.error('Error updating profile:', error));
        });
    }

    // Camera Functionality
    const video = document.getElementById('video');
    const startCameraBtn = document.getElementById('start-camera-btn');
    const stopCameraBtn = document.getElementById('stop-camera-btn');
    const captureLoginBtn = document.getElementById('capture-login-btn');
    const captureLogoutBtn = document.getElementById('capture-logout-btn');
    const submitStatusBtn = document.getElementById('submit-status-btn');
    const canvas = document.createElement('canvas');

    function startCamera() {
        console.log('Start camera button clicked');
        if (!window.isSecureContext) {
            alert('Camera access requires a secure connection (HTTPS or localhost). Please ensure your site is served over HTTPS.');
            return;
        }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            alert('getUserMedia is not supported in this browser. Please use a modern browser like Chrome, Firefox, or Safari.');
            return;
        }
        navigator.mediaDevices.getUserMedia({ video: true })
            .then(s => {
                console.log('Camera stream obtained successfully');
                stream = s;
                if (video) {
                    video.srcObject = stream;
                }
                if (startCameraBtn) startCameraBtn.style.display = 'none';
                if (stopCameraBtn) stopCameraBtn.style.display = 'block';
                if (captureLoginBtn) captureLoginBtn.style.display = 'block';
                if (captureLogoutBtn) captureLogoutBtn.style.display = 'block';
            })
            .catch(err => {
                console.error('Camera error:', err);
                let msg = 'Error accessing camera: ' + err.message;
                if (err.name === 'NotAllowedError') {
                    msg = 'Camera access was denied. Please allow camera permissions in your browser settings and try again.';
                } else if (err.name === 'NotFoundError') {
                    msg = 'No camera device found. Please ensure a camera is connected.';
                } else if (err.name === 'NotReadableError') {
                    msg = 'Camera is being used by another application. Please close other apps using the camera.';
                } else if (err.name === 'OverconstrainedError') {
                    msg = 'Camera constraints cannot be satisfied. Please try again.';
                } else if (err.name === 'SecurityError') {
                    msg = 'Security error occurred. Ensure the page is served over HTTPS.';
                }
                alert(msg);
            });
    }

    if (startCameraBtn) {
        startCameraBtn.addEventListener('click', startCamera);
    }

    if (stopCameraBtn) {
        stopCameraBtn.addEventListener('click', () => {
            console.log('Stop camera button clicked');
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                stream = null;
            }
            if (video) {
                video.srcObject = null;
            }
            if (startCameraBtn) startCameraBtn.style.display = 'block';
            if (stopCameraBtn) stopCameraBtn.style.display = 'none';
            if (captureLoginBtn) captureLoginBtn.style.display = 'none';
            if (captureLogoutBtn) captureLogoutBtn.style.display = 'none';
        });
    }

    function getLocation(successCallback, errorCallback) {
        if (!navigator.geolocation) {
            errorCallback(new Error('Geolocation is not supported by this browser.'));
            return;
        }
        navigator.geolocation.getCurrentPosition(
            (position) => {
                const lat = position.coords.latitude;
                const lng = position.coords.longitude;
                successCallback({ lat, lng });
            },
            (error) => {
                let message = 'Error accessing location: ';
                switch (error.code) {
                    case error.PERMISSION_DENIED:
                        message += 'Location access denied. Please allow location access to proceed with attendance.';
                        break;
                    case error.POSITION_UNAVAILABLE:
                        message += 'Location information is unavailable.';
                        break;
                    case error.TIMEOUT:
                        message += 'Location request timed out.';
                        break;
                    default:
                        message += 'An unknown error occurred.';
                        break;
                }
                errorCallback(new Error(message));
            },
            { timeout: 10000, enableHighAccuracy: true }
        );
    }

    function captureAndSubmit(endpoint, isLogin) {
        if (!video || !video.videoWidth || !video.videoHeight) {
            alert('Please ensure the camera is active and visible before capturing.');
            return;
        }

        getLocation(
            (geoPos) => {
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                canvas.getContext('2d').drawImage(video, 0, 0);
                canvas.toBlob((blob) => {
                    const formData = new FormData();
                    formData.append('face_image', blob, 'capture.jpg');
                    formData.append('latitude', geoPos.lat);
                    formData.append('longitude', geoPos.lng);
                    fetch(endpoint, { method: 'POST', body: formData })
                        .then(response => response.json())
                        .then(data => {
                            if (stopCameraBtn) stopCameraBtn.click();
                            if (data.success) {
                                const time = new Date().toLocaleString();
                                const action = isLogin ? 'Login' : 'Logout';
                                const photoKey = isLogin ? 'login_photo' : 'logout_photo';
                                alert(`${action} Successful! Time: ${time}\nAttendance Submitted\nPhoto captured\nLocation: ${geoPos.lat.toFixed(6)}, ${geoPos.lng.toFixed(6)}`);
                                window.location.reload();
                            } else {
                                alert(data.message || 'Capture failed.');
                            }
                        })
                        .catch(error => {
                            console.error(`Error capturing ${isLogin ? 'login' : 'logout'}:`, error);
                            alert('Network error during capture. Please try again.');
                        });
                }, 'image/jpeg');
            },
            (error) => {
                alert(error.message);
            }
        );
    }

    if (captureLoginBtn) {
        captureLoginBtn.addEventListener('click', () => {
            captureAndSubmit('/login_photo', true);
        });
    }

    if (submitStatusBtn) {
        submitStatusBtn.addEventListener('click', () => {
            const dailyStatus = document.getElementById('daily-status').value;
            if (!dailyStatus) {
                alert('Please enter your daily status report.');
                return;
            }
            fetch('/submit_daily_status', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `daily_status=${encodeURIComponent(dailyStatus)}`
            })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Daily status submitted successfully!');
                        location.reload();
                    } else {
                        alert(data.message || 'Submission failed.');
                    }
                })
                .catch(error => console.error('Error submitting status:', error));
        });
    }

    if (captureLogoutBtn) {
        captureLogoutBtn.addEventListener('click', () => {
            captureAndSubmit('/logout_photo', false);
        });
    }

    // Leave Request
    const submitLeaveBtn = document.getElementById('submit-leave-btn');
    if (submitLeaveBtn) {
        submitLeaveBtn.addEventListener('click', () => {
            const startDate = document.getElementById('leave-start').value;
            const endDate = document.getElementById('leave-end').value;
            const leaveType = document.getElementById('leave-type').value;
            if (!startDate || !endDate || !leaveType) {
                alert('Please fill in all leave request fields.');
                return;
            }
            alert(`Leave Request Submitted!\nStart: ${startDate}\nEnd: ${endDate}\nType: ${leaveType}`);
        });
    }

    // Notification Polling
    function checkNotifications() {
        fetch('/check_notifications')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.message) {
                    alert(`New Notification: ${data.message}`);
                    location.reload();
                }
            })
            .catch(error => console.error('Error checking notifications:', error));
    }
    setInterval(checkNotifications, 30000);
    checkNotifications();
});
