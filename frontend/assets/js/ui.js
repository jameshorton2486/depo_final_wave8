        function showToast(message, type = 'indigo') {
            const container = document.getElementById('toastContainer');
            const toast = document.createElement('div');
            toast.className = `p-3.5 bg-slate-900 border-l-4 rounded-r-xl border-${type}-500 text-white text-xs shadow-2xl flex items-center justify-between gap-3 animate-slide-in pointer-events-auto`;
            toast.innerHTML = `
                <span>${message}</span>
                <button onclick="this.parentElement.remove()" class="text-slate-500 hover:text-white">&times;</button>
            `;
            container.appendChild(toast);
            setTimeout(() => toast.remove(), 4500);
        }


        function getStageName(num) {
            const names = ["Case Intake", "Transcripts Engine", "Living Transcript Workspace", "Citation Insertion Pages", "Case Certification", "Format Export"];
            return names[num - 1];
        }

        // Trigger hidden inputs
        function triggerFileInput(id) {
            document.getElementById(id).click();
        }


window.showToast = showToast;
window.getStageName = getStageName;
window.triggerFileInput = triggerFileInput;
