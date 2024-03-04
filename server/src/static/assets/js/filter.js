document.addEventListener('DOMContentLoaded', function() {
    const searchBox = document.querySelector('.p-search-box__input');
    const tableRows = Array.from(document.querySelectorAll('.p-table--mobile-card tbody tr.searchable-row'));

    searchBox.addEventListener('input', function() {
        const searchTerm = searchBox.value.toLowerCase();

        tableRows.forEach(function(row) {
            const rowText = row.textContent.toLowerCase();
            const isMatch = rowText.includes(searchTerm);

            row.style.display = isMatch ? '' : 'none';
        });
    });
});
