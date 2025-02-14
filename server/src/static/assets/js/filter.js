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

/**
 * Sorts the specified table by the specified ordering
 * @param {HTMLTableCellElement} header
 * @param {HTMLTableElement} table
 * @param {String} newOrder
 */
function sortTable(header, table, newOrder) {
  // Get index of column based on position of header cell in <thead>
  // We assume there is only one row in the table head.
  var col = [].slice.call(table.tHead.rows[0].cells).indexOf(header);
  const sortDirectionMap = {
    none: 0,
    ascending: -1,
    descending: 1,
  };  

  // Reset all header sorts.
  var headerSorts = table.querySelectorAll('[aria-sort]');

  for (var i = 0, ii = headerSorts.length; i < ii; i += 1) {
    headerSorts[i].setAttribute('aria-sort', 'none');
  }

  // Set the new header sort.
  header.setAttribute('aria-sort', newOrder);

  // Get the direction of the sort and assume only one tbody.
  // For this example only assume one tbody.
  var direction = sortDirectionMap[newOrder];
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
    sortOrderFunc = defaultSortOrder;
    if (header.hasAttribute("use-outcome-sort")) {
      sortOrderFunc = outcomeSortOrder;
    }
    // Sort based on a cell contents
    newRows.sort(function (rowA, rowB) {
      return sortOrderFunc(rowA.cells[col], rowB.cells[col], direction);
    });
  }
  // Append each row into the table, replacing the current elements.
  for (i = 0, ii = body.rows.length; i < ii; i += 1) {
    body.appendChild(newRows[i]);
  }

  // Change url parameters based on sort order for the agents table
  if (table.id == "agentsTable") {
    var pageURL = new URL(window.location.href);
    pageURL.searchParams.set("tableId", table.id);
    pageURL.searchParams.set("headerId", header.id);
    pageURL.searchParams.set("sortOrder", newOrder);
    window.history.replaceState(null, null, pageURL);
  }
}

/**
 * Cycles through sort order states and applies the designated sort order to the
 * specified table.
 * @param {HTMLTableCellElement} header
 * @param {HTMLTableElement} table
 */
function cycleTableSort(header, table, reverse=false) {
  var SORTABLE_STATES = {
    none: 0,
    ascending: -1,
    descending: 1,
    ORDER: ['none', 'ascending', 'descending'],
  };

  // Based on the current aria-sort value, get the next state. Go backwards if cycle is reversed.
  var newOrder = (SORTABLE_STATES.ORDER.indexOf(header.getAttribute('aria-sort')) + 1) % 3;
  if (reverse) {
    newOrder = SORTABLE_STATES.ORDER.indexOf(header.getAttribute('aria-sort')) - 1;
    if (newOrder < 0) {
      newOrder += 3
    }
  }
  newOrder = SORTABLE_STATES.ORDER[newOrder];

  sortTable(header, table, newOrder);
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
    return direction * (parseInt(streakB) - parseInt(streakA));
  }

  // If A is failure and B is success, A should come before B
  return isFailureA ? -1 : 1;
}

function setupClickableHeader(table, header) {
  var reverse = false
  if (table.id == "agentsTable") {
    reverse = true;
  }
  header.addEventListener('click', function () {
    cycleTableSort(header, table, reverse);
  });
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

/**
 * Gets URL parameters and uses them to sort the specified table.
 * Currently only supports the agent table.
 */
function sortTableFromURL() {
  // Get url parameters for table sort ordering if specified
  const queryString = window.location.search;
  const urlParams = new URLSearchParams(queryString);
  const tableId = urlParams.get("tableId");
  // Only url parameters for the agents table is supported
  if (tableId != "agentsTable") {
    return;
  }
  const headerId = urlParams.get("headerId");
  var sortOrder = urlParams.get("sortOrder");
  const validSortOrders = ["ascending", "descending", "none"];
  if (!validSortOrders.includes(sortOrder)) {
    sortOrder = "none"
  } 
  var table = document.getElementById(tableId);
  var header = document.getElementById(headerId);
  if (table == null || header == null) {
    return;
  }
  sortTable(header, table, sortOrder);
}

// Make all tables on the page sortable.
var tables = document.querySelectorAll('table');
for (var i = 0, ii = tables.length; i < ii; i += 1) {
  setupSortableTable(tables[i]);
}
sortTableFromURL()
