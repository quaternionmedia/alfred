# Joining a shared alfred

Someone has shared their alfred with you: a video editor that runs in your
browser, on a phone, a tablet or a computer. It is not on the internet. It is
on a private network, and your device joins that network first, with a free
app called ZeroTier One. It takes about ten minutes, once.

You need three things from the person who invited you:

- **the invitation**, which has a network ID (sixteen letters and numbers) and
  a link;
- **an email address and a password** for alfred, sent separately;
- **their go-ahead** after you send them your device's ID (step 3).

## 1. Install ZeroTier One

| Your device | Where to get it |
|---|---|
| iPhone or iPad | the App Store: search for **ZeroTier One** |
| Android phone or tablet | Google Play: search for **ZeroTier One** |
| Windows | <https://www.zerotier.com/download/>, the Windows installer. When Windows asks to install a driver, allow it. |
| Mac (macOS 10.13 or newer) | <https://www.zerotier.com/download/>, the Mac installer |
| Linux | <https://www.zerotier.com/download/>, the one-line install it shows |

## 2. Join the network

Copy the network ID from your invitation and paste it; typing sixteen
characters is where mistakes happen.

- **On a phone or tablet:** open ZeroTier One, add a network, and paste the
  network ID. When your phone asks whether to allow a VPN connection, allow
  it. If there is a switch beside the network, turn it on.
- **On Windows or a Mac:** click the ZeroTier icon (on Windows, in the
  corner of the taskbar, perhaps behind the **^** arrow; on a Mac, in the menu
  bar at the top), choose **Join New Network...**, paste the network ID and
  click **Join**. If Windows asks whether this computer should be
  discoverable on the network, **No** is fine.
- **On Linux:** `sudo zerotier-cli join` followed by the network ID.

## 3. Send your device ID

ZeroTier gives your device an ID of its own: ten letters and numbers, such as
`89e92ceee5`. Depending on where you look, it is called the **address**, the
**device ID** or the **node ID**. It is in the ZeroTier icon's menu on a
computer, near the top of the app on a phone, and on Linux
`sudo zerotier-cli info` prints it.

Send it to the person who invited you. Until they let your device in,
ZeroTier shows the network as **access denied**; that is expected.

## 4. Open alfred

When they tell you that you are in, open the link from your invitation in
your browser. On the share these pages describe it is
`http://10.173.20.1:17320`. Type or paste it exactly as it is: it starts
`http://`, not `https://`, and ends with `:17320`.

Your browser may say the page is **not secure**. That is expected: alfred is
not on the internet, and ZeroTier encrypts everything between your device
and it.

**On a phone,** put alfred on your home screen so it opens like an app: in
Safari on an iPhone or iPad, the **Share** button, then **Add to Home
Screen**; in Chrome on Android, the **⋮** menu, then **Add to Home screen** (or
**Install app**).

## 5. Log in

Log in with the email address and password you were sent.

- **Do not press Create an account.** This alfred takes no new accounts; the
  person who invited you makes them.
- **Forgot password sends no email here.** To change or reset your password,
  ask the person who invited you.

Then [A first video](journeys.md#first-video) is a good place to start, and
[On a phone](journeys.md#on-a-phone) says how the editor works on a small
screen. The **User documentation** link at the foot of alfred's login page
opens these pages.

## If alfred does not open

Check these in order:

1. **ZeroTier is on.** On a phone, the network's switch is on. On a
   computer, the network is ticked in the ZeroTier icon's menu.
2. **You have been let in.** If ZeroTier still says access denied, ask.
3. **No other VPN is on.** A phone runs one VPN at a time, so a VPN from
   work or a privacy app turns ZeroTier off. Turn the other one off while you
   use alfred.
4. **The link is exact**: `http://`, and `:17320` at the end.
5. **The computer alfred runs on is awake.** When it sleeps or is off, alfred
   is too. Ask.

A phone or laptop managed by an employer may not be allowed to install a VPN
app at all; use another device.

## Good to know

- **This is a working copy.** It runs alfred as it is being built, and it
  changes between visits. What you make stays, unless the person who runs it
  restores an earlier copy.
- **The person who runs it can see what you upload.** Upload what you are
  happy for the team to see.
- **Big videos take a while** to upload from a phone, and use your data
  allowance away from Wi-Fi.
- **When you are done,** remove the network in ZeroTier (on a computer: the
  icon's menu, the network's **Network Details**, then **Delete Network**),
  or uninstall the app.
