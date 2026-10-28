/* ===== BOOKING SWITCH (one setting for the whole site) =====
   false = washer recruitment only: everything about customer bookings is hidden on every page.
   true  = bookings open: prices, booking form, customer terms and booking wording appear.
   Preview without switching on: add ?booking=on to any page address. */
var BOOKING_ENABLED = false;

/* ===== WASHER LOGIN SWITCH =====
   false = the washer login link is hidden and /washers/ says "opening soon".
   true  = washers can sign up, log in and do the training.
   Preview without switching on: add ?login=on to any page address. */
var WASHER_LOGIN_ENABLED = false;

(function(){
  var q=location.search, on=BOOKING_ENABLED;
  if (/[?&]booking=on/.test(q) || location.hash==="#preview-booking") on=true;
  if (/[?&]booking=off/.test(q)) on=false;
  var login=WASHER_LOGIN_ENABLED;
  if (/[?&]login=on/.test(q)) login=true;
  if (/[?&]login=off/.test(q)) login=false;
  document.documentElement.classList.add(on ? "f-booking" : "f-washers", login ? "f-login" : "f-no-login");
  var st=document.createElement("style");
  st.textContent='html.f-washers [data-show="booking"]{display:none!important}html.f-booking [data-show="washers"]{display:none!important}html.f-no-login [data-show="washer-login"]{display:none!important}';
  document.head.appendChild(st);
  window.__BOOKING_ON=on;
  window.__LOGIN_ON=login;
})();
