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
