'use strict';

// ── Toast notifications ─────────────────────────────────────────────────
function showToast(msg, type = 'ok') {
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2800);
}

// ── Feedback submission ─────────────────────────────────────────────────
function submitFeedback(articleId, rating, btn) {
  const card = document.getElementById(`article-${articleId}`);
  const fd = new FormData();
  fd.append('article_id', articleId);
  fd.append('rating', rating);

  // Preserve existing note if any
  const noteInput = document.getElementById(`note-input-${articleId}`);
  if (noteInput) fd.append('note', noteInput.value);

  fetch('/api/feedback', { method: 'POST', body: fd })
    .then(r => r.json())
    .then(data => {
      if (data.status !== 'ok') throw new Error();

      // Reset all feedback buttons in this card
      card.querySelectorAll('.btn-feedback').forEach(b => b.classList.remove('active'));

      // Toggle off if same rating already active
      const wasActive = btn.classList.contains('active');
      if (!wasActive) {
        btn.classList.add('active');
      }

      // Update card border
      card.classList.remove('card-liked', 'card-disliked');
      if (!wasActive) {
        if (rating === 'liked') card.classList.add('card-liked');
        else if (rating === 'disliked') card.classList.add('card-disliked');
      }

      showToast(wasActive ? 'Feedback cleared' : (rating === 'liked' ? '👍 Marked as liked' : '👎 Marked as disliked'));
    })
    .catch(() => showToast('Failed to save feedback', 'err'));
}

// ── Note toggle ─────────────────────────────────────────────────────────
function toggleNote(articleId) {
  const form = document.getElementById(`note-${articleId}`);
  if (!form) return;
  const visible = form.style.display !== 'none';
  form.style.display = visible ? 'none' : 'flex';
  if (!visible) document.getElementById(`note-input-${articleId}`)?.focus();
}

// ── Note save ───────────────────────────────────────────────────────────
function submitNote(articleId) {
  const noteInput = document.getElementById(`note-input-${articleId}`);
  if (!noteInput) return;

  const card = document.getElementById(`article-${articleId}`);
  // Get current active rating
  const activeBtn = card.querySelector('.btn-feedback.active');
  const rating = activeBtn
    ? (activeBtn.classList.contains('btn-like') ? 'liked' : 'disliked')
    : 'neutral';

  const fd = new FormData();
  fd.append('article_id', articleId);
  fd.append('rating', rating);
  fd.append('note', noteInput.value.trim());

  fetch('/api/feedback', { method: 'POST', body: fd })
    .then(r => r.json())
    .then(data => {
      if (data.status !== 'ok') throw new Error();
      // Update saved note display
      const savedNote = card.querySelector('.saved-note');
      if (savedNote) {
        savedNote.textContent = noteInput.value.trim() ? `"${noteInput.value.trim()}"` : '';
      }
      document.getElementById(`note-${articleId}`).style.display = 'none';
      showToast('Note saved');
    })
    .catch(() => showToast('Failed to save note', 'err'));
}

// ── Topic controls ──────────────────────────────────────────────────────
function toggleTopic(topicId, active) {
  const fd = new FormData();
  fd.append('active', active ? 'true' : 'false');
  fetch(`/api/topics/${topicId}`, { method: 'POST', body: fd })
    .then(r => r.json())
    .then(() => showToast(active ? 'Topic enabled' : 'Topic disabled'))
    .catch(() => showToast('Failed to update topic', 'err'));
}

function updateWeight(topicId, value) {
  const fd = new FormData();
  fd.append('weight', value);
  fetch(`/api/topics/${topicId}`, { method: 'POST', body: fd })
    .then(r => r.json())
    .then(() => showToast(`Weight set to ${parseFloat(value).toFixed(1)}`))
    .catch(() => showToast('Failed to update weight', 'err'));
}

function saveQueries(topicId) {
  const textarea = document.getElementById(`queries-${topicId}`);
  if (!textarea) return;
  const fd = new FormData();
  fd.append('search_queries', textarea.value);
  fetch(`/api/topics/${topicId}`, { method: 'POST', body: fd })
    .then(r => r.json())
    .then(() => showToast('Queries saved'))
    .catch(() => showToast('Failed to save queries', 'err'));
}

// ── Pipeline trigger forms ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form[action="/api/pipeline/run"]').forEach(form => {
    form.addEventListener('submit', e => {
      e.preventDefault();
      const runType = form.querySelector('[name="run_type"]').value;
      const fd = new FormData(form);
      fetch('/api/pipeline/run', { method: 'POST', body: fd })
        .then(r => r.json())
        .then(() => {
          showToast(`${runType === 'daily' ? 'Daily pipeline' : 'Weekly digest'} started`);
          // Reload after a moment so the running indicator appears
          setTimeout(() => location.reload(), 800);
        })
        .catch(() => showToast('Failed to start pipeline', 'err'));
    });
  });
});
