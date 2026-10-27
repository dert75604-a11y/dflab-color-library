/* DF-LAB 公开色卡桥。
   读取 data/colors.json（飞书「公开上架」导出）。
   只在有公开条目时重绘「全部色卡」浮层。
   不改手势缩放、宏图横滑、木种行横滑，也不替换现有手势图。
   文件为空、失败，或没有可显示的图时，页面保持现在的样子。 */
(function () {
  var JSON_URL = new URL('data/colors.json', document.baseURI).href;

  function safeSrc(value) {
    if (!value || typeof value !== 'string') return '';
    if (value.indexOf('data:') === 0 || value.indexOf('..') !== -1) return '';
    if (/^\/assets\/colors\/[A-Za-z0-9._-]+$/.test(value)) return value;
    if (/^https?:\/\//i.test(value)) return value;
    return '';
  }

  function project(item) {
    if (!item || typeof item !== 'object') return null;
    var image = safeSrc(item.image);
    if (!item.code || !image) return null;
    var tags = [];
    (item.tags || []).forEach(function (tag) {
      if (typeof tag === 'string' && tag && tags.indexOf(tag) === -1) tags.push(tag);
    });
    return {
      code: String(item.code),
      name: item.name || '',
      color: item.color || '',
      finish: item.finish || '',
      species: item.species || '',
      image: image,
      imageCloseup: safeSrc(item.imageCloseup),
      uploader: item.uploader || 'DF-LAB',
      tags: tags
    };
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function closeLibrary() {
    var lib = document.getElementById('library');
    if (!lib) return;
    lib.classList.remove('open');
    lib.hidden = true;
    document.body.style.overflow = '';
  }

  function showOnHero(item) {
    var main = document.getElementById('mainImg');
    var macro0 = document.getElementById('macroImg0');
    var macro1 = document.getElementById('macroImg1');
    if (main) {
      main.src = item.image;
      main.alt = item.name || item.code;
    }
    var closeup = item.imageCloseup || item.image;
    if (macro0) macro0.src = closeup;
    if (macro1) macro1.src = closeup;
    var title = document.querySelector('header.bar .h1');
    if (title) title.textContent = item.name || item.code;
    var sub = document.querySelector('header.bar .sub');
    if (sub) sub.textContent = [item.code, item.species, item.finish].filter(Boolean).join(' · ');
    var libSub = document.getElementById('libSub');
    if (libSub) libSub.textContent = item.name || item.code;
    var footName = document.getElementById('footName');
    if (footName) footName.textContent = (item.name || item.code) + ' · ' + item.code;
    var footMeta = document.getElementById('footMeta');
    if (footMeta) footMeta.textContent = [item.species, item.finish].filter(Boolean).join(' · ');
    closeLibrary();
    window.scrollTo(0, 0);
  }

  function paintLibrary(items) {
    var grid = document.getElementById('libraryGrid');
    var filters = document.getElementById('libraryFilters');
    var countEl = document.getElementById('libraryCount');
    if (!grid) return false;
    clear(grid);
    if (filters) clear(filters);

    var species = ['全部'];
    items.forEach(function (item) {
      var name = item.species || '其他';
      if (species.indexOf(name) < 0) species.push(name);
    });

    var cards = [];
    items.forEach(function (item) {
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'lib-card';
      button.setAttribute('data-wood', item.species || '其他');
      button.setAttribute('data-code', item.code);
      var img = document.createElement('img');
      img.src = item.image;
      img.alt = item.name || item.code;
      var cap = document.createElement('span');
      cap.className = 'lib-card-name';
      cap.textContent = (item.name || item.code) + ' ' + item.code;
      button.appendChild(img);
      button.appendChild(cap);
      button.addEventListener('click', function () { showOnHero(item); });
      grid.appendChild(button);
      cards.push(button);
    });

    function apply(name) {
      var shown = 0;
      cards.forEach(function (card) {
        var ok = name === '全部' || card.getAttribute('data-wood') === name;
        card.hidden = !ok;
        if (ok) shown += 1;
      });
      if (countEl) countEl.textContent = shown + ' 色';
    }

    species.forEach(function (name, idx) {
      if (!filters) return;
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'wood-chip' + (idx === 0 ? ' on' : '');
      chip.textContent = name;
      chip.addEventListener('click', function () {
        Array.prototype.forEach.call(filters.querySelectorAll('.wood-chip'), function (node) {
          node.classList.remove('on');
        });
        chip.classList.add('on');
        apply(name);
      });
      filters.appendChild(chip);
    });
    apply('全部');
    return true;
  }

  function apply(list) {
    var items = [];
    (list || []).forEach(function (item) {
      var next = project(item);
      if (next) items.push(next);
    });
    window.DF_LAB_PUBLIC_COLORS = items;
    if (!items.length) return items;
    paintLibrary(items);
    return items;
  }

  window.DF_LAB_APPLY_PUBLIC_COLORS = apply;

  fetch(JSON_URL)
    .then(function (res) {
      if (!res.ok) throw new Error('load');
      return res.json();
    })
    .then(function (data) {
      if (!Array.isArray(data)) throw new Error('shape');
      apply(data);
    })
    .catch(function () {
      window.DF_LAB_PUBLIC_COLORS = window.DF_LAB_PUBLIC_COLORS || [];
    });
})();
