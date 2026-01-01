// static/js/admin.js
document.addEventListener("DOMContentLoaded", function () {
    const navItems = document.querySelectorAll('.sidebar-nav li[data-section]');
    const sections = document.querySelectorAll('.content-section');
    const sidebar = document.getElementById('sidebar');
    const viewSelect = document.getElementById('view-select');
    const searchInput = document.getElementById('search-input');
    const searchBtn = document.getElementById('search-btn');
    const attendanceTable = document.getElementById('attendance-table');
    const allAttendanceSection = document.getElementById('all-attendance-section');
    const editUserModal = new bootstrap.Modal(document.getElementById('editUserModal'));

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
                if (sectionId === 'export') {
                    window.location.href = '/export_page';
                }
            }
        });
    });

    // Admin Profile Edit
    const adminEditProfileBtn = document.getElementById('admin-edit-profile-btn');
    const adminSaveProfileBtn = document.getElementById('admin-save-profile-btn');
    const adminEmailInput = document.getElementById('admin-email');
    const adminNewFaceImageInput = document.getElementById('admin-new-face-image');
    const adminProfilePic = document.getElementById('admin-profile-pic');
    const adminEmailDisplay = document.getElementById('admin-email-display');

    adminEditProfileBtn.addEventListener('click', () => {
        adminEmailInput.style.display = 'block';
        adminNewFaceImageInput.style.display = 'block';
        adminEmailDisplay.style.display = 'none';
        adminEditProfileBtn.style.display = 'none';
        adminSaveProfileBtn.style.display = 'block';
    });

    adminNewFaceImageInput.addEventListener('change', (event) => {
        const file = event.target.files[0];
        if (file) {
            adminProfilePic.src = URL.createObjectURL(file);
        }
    });

    adminSaveProfileBtn.addEventListener('click', () => {
        const formData = new FormData();
        formData.append('email', adminEmailInput.value);
        if (adminNewFaceImageInput.files[0]) {
            formData.append('face_image', adminNewFaceImageInput.files[0]);
        }
        fetch('/update_profile', { method: 'POST', body: formData })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Admin profile updated successfully!');
                    adminEmailDisplay.textContent = adminEmailInput.value;
                    adminEmailInput.style.display = 'none';
                    adminNewFaceImageInput.style.display = 'none';
                    adminEmailDisplay.style.display = 'inline';
                    adminEditProfileBtn.style.display = 'block';
                    adminSaveProfileBtn.style.display = 'none';
                    location.reload();
                } else {
                    alert(data.message);
                }
            })
            .catch(error => console.error('Error updating admin profile:', error));
    });

    // View Selector
    viewSelect.addEventListener('change', (e) => {
        const url = new URL(window.location);
        url.searchParams.set('view', e.target.value);
        window.location.href = url.toString();
    });

    // Search Functionality
    searchBtn.addEventListener('click', performSearch);
    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') performSearch();
    });

    function performSearch() {
        const query = searchInput.value.trim();
        const url = new URL(window.location);
        if (query) {
            url.searchParams.set('search', query);
        } else {
            url.searchParams.delete('search');
        }
        window.location.href = url.toString();
    }

    // Update Attendance Status
    attendanceTable.addEventListener('change', (e) => {
        if (e.target.classList.contains('status-select')) {
            const attendanceId = e.target.dataset.id;
            const status = e.target.value;
            const formData = new FormData();
            formData.append('status', status);
            fetch(`/update_attendance_status/${attendanceId}`, { method: 'POST', body: formData })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('Status updated!');
                    } else {
                        alert(data.message);
                        e.target.value = e.target.dataset.previousValue || 'Absent'; // Revert
                    }
                })
                .catch(error => {
                    console.error('Error updating status:', error);
                    alert('Error updating status');
                });
        }
    });

    // Manage Users - Edit Button
    const editUserBtns = document.querySelectorAll('.edit-user-btn');
    editUserBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const userId = e.target.dataset.id;
            const row = e.target.closest('tr');
            document.getElementById('edit-user-id').value = userId;
            document.getElementById('edit-username').value = row.cells[1].textContent;
            document.getElementById('edit-email').value = row.cells[2].textContent;
            document.getElementById('edit-position').value = row.cells[3].textContent;
            editUserModal.show();
        });
    });

    // Save User Changes
    document.getElementById('save-user-btn').addEventListener('click', () => {
        const userId = document.getElementById('edit-user-id').value;
        const formData = new FormData();
        formData.append('username', document.getElementById('edit-username').value);
        formData.append('email', document.getElementById('edit-email').value);
        formData.append('position', document.getElementById('edit-position').value);
        const faceFile = document.getElementById('edit-face-image').files[0];
        if (faceFile) {
            formData.append('face_image', faceFile);
        }
        fetch(`/admin_update_user/${userId}`, { method: 'POST', body: formData })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('User updated successfully!');
                    editUserModal.hide();
                    location.reload();
                } else {
                    alert(data.message);
                }
            })
            .catch(error => {
                console.error('Error updating user:', error);
                alert('Error updating user');
            });
    });

    // Upload Rota
    const uploadRotaForm = document.getElementById('upload-rota-form');
    uploadRotaForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const formData = new FormData();
        formData.append('rota_image', document.getElementById('rota-image').files[0]);
        fetch('/upload_rota', { method: 'POST', body: formData })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Rota uploaded successfully!');
                    location.reload();
                } else {
                    alert(data.message);
                }
            })
            .catch(error => {
                console.error('Error uploading rota:', error);
                alert('Error uploading rota');
            });
    });

    // Send Notification
    const sendNotificationForm = document.getElementById('send-notification-form');
    sendNotificationForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const formData = new FormData();
        formData.append('message', document.getElementById('notification-message').value);
        fetch('/send_notification', { method: 'POST', body: formData })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('Notification sent successfully!');
                    document.getElementById('notification-message').value = '';
                } else {
                    alert(data.message);
                }
            })
            .catch(error => {
                console.error('Error sending notification:', error);
                alert('Error sending notification');
            });
    });

    // Show All Attendance (toggle)
    const toggleAllAttendance = document.getElementById('toggle-all-attendance');
    if (toggleAllAttendance) {
        toggleAllAttendance.addEventListener('click', () => {
            allAttendanceSection.style.display = allAttendanceSection.style.display === 'none' ? 'block' : 'none';
        });
    }
});
