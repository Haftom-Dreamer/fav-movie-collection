document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.live-search').forEach(input => {
        let timeout = null;
        
        // Wrap input in relative container
        const wrapper = document.createElement('div');
        wrapper.className = 'autocomplete-wrapper';
        wrapper.style.position = 'relative';
        wrapper.style.flex = '1';
        wrapper.style.display = 'flex';
        input.parentNode.insertBefore(wrapper, input);
        wrapper.appendChild(input);
        
        const dropdown = document.createElement('div');
        dropdown.className = 'autocomplete-dropdown';
        wrapper.appendChild(dropdown);
        
        input.addEventListener('input', (e) => {
            clearTimeout(timeout);
            const q = e.target.value.trim();
            const type = input.dataset.type || 'movie';
            
            if (q.length < 2) {
                dropdown.style.display = 'none';
                return;
            }
            
            timeout = setTimeout(() => {
                fetch(`/api/search_${type}?q=${encodeURIComponent(q)}`)
                    .then(r => r.json())
                    .then(data => {
                        if (data.length === 0) {
                            dropdown.style.display = 'none';
                            return;
                        }
                        dropdown.innerHTML = data.map(item => `
                            <div class="autocomplete-item" data-id="${item.id}" data-title="${escapeHtml(item.title)}">
                                ${escapeHtml(item.title)} <span style="opacity:0.6;font-size:0.8rem;">${item.year ? `(${item.year})` : ''}</span>
                            </div>
                        `).join('');
                        dropdown.style.display = 'block';
                    });
            }, 300);
        });
        
        dropdown.addEventListener('click', (e) => {
            const item = e.target.closest('.autocomplete-item');
            if (item) {
                input.value = item.dataset.title;
                dropdown.style.display = 'none';
                // Automatically submit the form
                const form = input.closest('form');
                if (form) form.submit();
            }
        });
        
        document.addEventListener('click', (e) => {
            if (!wrapper.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });
    });
});

function escapeHtml(unsafe) {
    return (unsafe || '').replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
