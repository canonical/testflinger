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

function sortTable(header, table, sortOrderFunc) {
  var SORTABLE_STATES = {
    none: 0,
    ascending: -1,
    descending: 1,
    ORDER: ['none', 'ascending', 'descending'],
  };

  // Get index of column based on position of header cell in <thead>
  // We assume there is only one row in the table head.
  var col = [].slice.call(table.tHead.rows[0].cells).indexOf(header);

  // Based on the current aria-sort value, get the next state.
  var newOrder = SORTABLE_STATES.ORDER.indexOf(header.getAttribute('aria-sort')) + 1;
  newOrder = newOrder > SORTABLE_STATES.ORDER.length - 1 ? 0 : newOrder;
  newOrder = SORTABLE_STATES.ORDER[newOrder];

  // Reset all header sorts.
  var headerSorts = table.querySelectorAll('[aria-sort]');

  for (var i = 0, ii = headerSorts.length; i < ii; i += 1) {
    headerSorts[i].setAttribute('aria-sort', 'none');
  }

  // Set the new header sort.
  header.setAttribute('aria-sort', newOrder);

  // Get the direction of the sort and assume only one tbody.
  // For this example only assume one tbody.
  var direction = SORTABLE_STATES[newOrder];
  var body = table.tBodies[0];

  // Convert the HTML element list to an array.
  var newRows = [].slice.call(body.rows, 0);

  // If the direction is 0 - aria-sort="none".
  if (direction === 0) {
    // Reset to the default order.
    newRows.sort(function (a, b) {
      return a.getAttribute('data-index') - b.getAttribute('data-index');
    });
  } else {
    // Sort based on a cell contents
    newRows.sort(function (rowA, rowB) {
      return sortOrderFunc(rowA.cells[col], rowB.cells[col], direction);
    });
  }
  // Append each row into the table, replacing the current elements.
  for (i = 0, ii = body.rows.length; i < ii; i += 1) {
    body.appendChild(newRows[i]);
  }
}

/**
 * Default sort order for generic table columns. Uses an alphebetical ordering.
 * @param {HTMLTableCellElement} cellA
 * @param {HTMLTableCellElement} cellB
 * @param {Number} direction
 */
function defaultSortOrder(cellA, cellB, direction) {
  // Trim the cell contents.
  var contentA = cellA.textContent.trim();
  var contentB = cellB.textContent.trim();
  return contentA < contentB ? direction : -direction;
}

/**
 * Custom ordering function to sort the provisioning streak column in the agents table.
 * Succeses and failures are grouped, then the streak number is always ordered
 * in descending order.
 * @param {HTMLTableCellElement} cellA
 * @param {HTMLTableCellElement} cellB
 * @param {Number} direction
 */
function outcomeSortOrder(cellA, cellB, direction) {
  // Trim the provision streak number.
  var streakA = cellA.getElementsByClassName("provision-streak")[0].textContent.trim();
  var streakB = cellB.getElementsByClassName("provision-streak")[0].textContent.trim();
  // Get success/failure icon of the row
  var isFailureA = cellA.getElementsByClassName("p-icon--warning").length > 0;
  var isFailureB = cellB.getElementsByClassName("p-icon--warning").length > 0;
  // If both are failures or both are successes, we do a simple comparison
  if (isFailureA == isFailureB) {
    return parseInt(streakB) - parseInt(streakA);
  }

  // If A is failure and B is success, A should come before B in descending order
  return isFailureA ? -direction : direction;
}

function setupClickableHeader(table, header) {
  if (header.hasAttribute("use-outcome-sort")) {
    header.addEventListener('click', function () {
      sortTable(header, table, outcomeSortOrder);
    });
  } else {
    header.addEventListener('click', function () {
      sortTable(header, table, defaultSortOrder);
    });
  }
}

/**
 * Initializes a sortable table by assigning event listeners to sortable column headers.
 * @param {HTMLTableElement} table
 */
function setupSortableTable(table) {
  // For this example, assume only one tbody.
  var rows = table.tBodies[0].rows;
  // Set an index for the default order.
  for (var row = 0, totalRows = rows.length; row < totalRows; row += 1) {
    rows[row].setAttribute('data-index', row);
  }

  // Select sortable column headers.
  var clickableHeaders = table.querySelectorAll('th[aria-sort]');
  // Attach the click event for each header.
  for (var i = 0, ii = clickableHeaders.length; i < ii; i += 1) {
    setupClickableHeader(table, clickableHeaders[i]);
  }
}

// Make all tables on the page sortable.
var tables = document.querySelectorAll('table');

for (var i = 0, ii = tables.length; i < ii; i += 1) {
  setupSortableTable(tables[i]);
}
