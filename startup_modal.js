// startup_modal.js – presents a neutral startup screen and controls graph loading

// Add overlay modal when the DOM is ready
document.addEventListener('DOMContentLoaded', function () {
  // Create modal div
  const modal = document.createElement('div');
  modal.id = 'startup-modal';
  Object.assign(modal.style, {
    position: 'fixed',
    top: 0,
    left: 0,
    width: '100%',
    height: '100%',
    background: '#1a1a2e',
    color: '#e0e0e0',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 200,
  });
  modal.innerHTML = `
    <h2 style="margin-bottom:12px;">Welcome to wikigraph</h2>
    <p style="margin-bottom:20px;">Choose a mode to start:</p>
    <button id="start-top-btn" class="btn-primary" style="margin:4px;">Generate Top 100 (Hatnote)</button>
    <button id="start-custom-btn" class="btn-primary" style="margin:4px;">Create Custom List</button>
  `;
  document.body.appendChild(modal);

  // Prevent automatic graph loading until user decides
  window.autoLoadEnabled = false;
  // Wrap loadGraph (if already defined) to respect the flag
  if (typeof window.loadGraph === 'function') {
    const originalLoadGraph = window.loadGraph;
    window.loadGraph = function (url) {
      if (window.autoLoadEnabled) {
        originalLoadGraph(url);
      } else {
        console.log('Auto load suppressed – awaiting user action');
      }
    };
  }

  // Helper to hide the modal
  function hideModal() {
    modal.style.display = 'none';
  }

  // Top‑100 button – enable auto‑load and trigger the normal date load
  const topBtn = document.getElementById('start-top-btn');
  topBtn.addEventListener('click', function () {
    window.autoLoadEnabled = true;
    // Ensure date mode UI is active (default mode is date)
    if (typeof switchMode === 'function') switchMode('date');
    // Trigger a load for the current date picker value
    if (typeof onDateChange === 'function') onDateChange();
    hideModal();
  });

  // Custom list button – switch to custom mode; user will press Build Graph later
  const customBtn = document.getElementById('start-custom-btn');
  customBtn.addEventListener('click', function () {
    if (typeof switchMode === 'function') switchMode('custom');
    hideModal();
    // No auto‑load – user can edit the textarea and click the existing Build Graph button
  });
});
