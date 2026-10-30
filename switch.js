/* ===== BOOKING SWITCH (one setting for the whole site) =====
   false = washer recruitment only: everything about customer bookings is hidden on every page.
   true  = bookings open: prices, booking form, customer terms and booking wording appear.
   Preview without switching on: add ?booking=on to any page address. */
var BOOKING_ENABLED = false;
(function(){
  var q=location.search, on=BOOKING_ENABLED;
  if (/[?&]booking=on/.test(q) || location.hash==="#preview-booking") on=true;
  if (/[?&]booking=off/.test(q)) on=false;
  document.documentElement.classList.add(on ? "f-booking" : "f-washers");
  var st=document.createElement("style");
  st.textContent='html.f-washers [data-show="booking"]{display:none!important}html.f-booking [data-show="washers"]{display:none!important}';
  document.head.appendChild(st);
  window.__BOOKING_ON=on;
})();

/* ===== BRAND IN THE BROWSER TAB (runs on every page) =====
   Adds the sparqle icon and shows "Sparqle" as the tab title: "Sparqle" on the home page,
   "Privacy Policy · Sparqle" on the others. Keeps working if a page changes its title later. */
(function(){
  var l=document.createElement("link"); l.rel="icon"; l.type="image/svg+xml"; l.href="favicon.svg"; document.head.appendChild(l);
  function brand(){
    var t=document.title;
    if(/^(Earn cash washing cars|Mobile car wash)/.test(t)) document.title="Sparqle";
    else if(/ \u00b7 sparqle\.com\.au$/.test(t)) document.title=t.replace(/ \u00b7 sparqle\.com\.au$/," \u00b7 Sparqle");
  }
  brand();
  var te=document.querySelector("title");
  if(te && window.MutationObserver) new MutationObserver(brand).observe(te,{childList:true,characterData:true,subtree:true});
})();
