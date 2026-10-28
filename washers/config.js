/* ===== WASHER AREA SETTINGS =====
   Fill in the two Supabase values from your project (Project Settings > API Keys).
   Both are safe to publish: the key only allows what the access rules in
   supabase/schema.sql allow. Never put the "secret" or "service_role" key here. */
window.SPARQLE_CONFIG = {
  supabaseUrl: "",      // e.g. "https://abcdefghijklmnop.supabase.co"
  supabaseKey: "",      // the "publishable" key (sb_publishable_...) or the legacy "anon public" key

  // New sign-ups and quiz results are emailed here, through FormSubmit like the site's other forms.
  notifyEndpoint: "https://formsubmit.co/ajax/admin@elitedigitalconsulting.com.au",
  contactEmail: "hello@sparqle.com.au"
};
