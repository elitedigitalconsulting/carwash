# Washer login and training: setup

The washer area lives at `www.sparqle.com.au/washers/`. Washers create an account, you approve them, and they do the training and quiz. Quiz results are saved in the database and emailed to admin@elitedigitalconsulting.com.au.

It stays hidden until you switch it on (step 6). Logins and data are handled by [Supabase](https://supabase.com), which is free at this size.

## 1. Create the Supabase project (about 10 minutes)

1. Sign up at supabase.com and click **New project**.
2. Name it `sparqle`, set a strong database password and save it in your password manager.
3. For **Region**, choose **Sydney (ap-southeast-2)** so washer details stay in Australia.

## 2. Set up the database

1. Open **SQL Editor**, then **New query**.
2. Paste in all of `supabase/schema.sql` from this repo, then click **Run**.
3. Open a new query, paste in all of `training-content.sql`, then click **Run**. This loads the modules, quiz questions and answers.

`training-content.sql` holds the quiz answers, so it is **not** in this repo, because anyone can read the files on the website. Keep it somewhere private, like your Google Drive. To change the course later, edit that file and run it again.

## 3. Login settings

Under **Authentication**:

1. **URL Configuration:**
   - Set **Site URL** to `https://www.sparqle.com.au/washers/`.
   - Under **Redirect URLs**, add `https://www.sparqle.com.au/washers/` and `https://www.sparqle.com.au/washers/?login=on`.
2. **Sign In / Providers > Email:** leave **Confirm email** turned on.

   This matters for security. Admin access is given to admin@elitedigitalconsulting.com.au only once that email is confirmed, so nobody else can claim it.
3. **Emails > SMTP Settings:** turn on custom SMTP. Supabase's built-in email only sends to your own team's addresses and a handful an hour, so washers wouldn't get their confirmation emails without this.
   - The simplest option is [Resend](https://resend.com). Its free tier covers 3,000 emails a month. Verify the `sparqle.com.au` domain there by adding the DNS records it gives you, then copy its SMTP details into Supabase.
   - Set the sender to something like `Sparqle <hello@sparqle.com.au>`.
4. **Emails > Templates:** optionally reword the "Confirm signup" and "Reset password" emails to sound like Sparqle.

## 4. Connect the website

1. In Supabase, open **Project Settings > API Keys**.
2. Copy the **Project URL** and the **publishable** key (or the legacy **anon public** key).
3. Put both in `washers/config.js`.

Never use the **secret** or **service_role** key there.

## 5. Create your admin account

1. Open `https://www.sparqle.com.au/washers/?login=on`.
2. Click **Create account** and sign up with **admin@elitedigitalconsulting.com.au**.
3. Confirm the email, then log in. You'll see the **Washers** tab.

## 6. Go live

1. In `switch.js`, set `var WASHER_LOGIN_ENABLED = true;`. This adds "Washer login" to the site header and footer and opens the sign-up page.
2. Add Supabase to the privacy policy (`privacy.html`, under "Service providers"). Suggested wording:

   > Washer accounts and training results are stored with Supabase (supabase.com) on servers in Sydney.

3. Send your washers the link: `https://www.sparqle.com.au/washers/`.

## Day to day

- **New sign-ups:** you get an email titled "New washer account waiting for approval". Log in, open **Washers** and click **Approve**. Washers aren't emailed when you approve them, so text them.
- **Quiz results:** each attempt emails you a "Washer quiz PASSED" or "NOT PASSED" message, listing any questions they got wrong. The **Washers** tab shows each washer's best score and attempts.
- **Removing someone:** click **Turn off access**. They can still log in, but they can't see the training.
- **Washers get 5 quiz attempts a day.**
- **Adding another admin:** in the SQL Editor, run `insert into admins (email) values ('their@email');`.

The notification emails go through FormSubmit, like the site's other forms. If FormSubmit sends an "activate this form" email the first time, click the link in it.
