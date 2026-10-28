# Washer training video

Generates the training video with Google's Gemini API (Veo for video, Gemini text-to-speech for the voiceover) and assembles it with ffmpeg. Scenes, prompts, voiceover lines and captions are in `scenes.json`.

Needs `GEMINI_API_KEY`: a Google AI Studio key from a project with billing on (Veo isn't on the free tier).

1. `python3 video/make_video.py models`: check which models the key can use.
2. `python3 video/make_video.py clip A1`: make one test scene and check it before spending more.
3. `python3 video/make_video.py clips`: make the rest. It can be re-run; finished clips are skipped.
4. Review frames in `video/out/frames/`. Re-make a bad take with `clip <ID> <takes>`, then `pick <ID> <take>`.
5. `python3 video/make_video.py voice`, then `build`. The result is `video/out/sparqle-washer-training.mp4`.

`selftest` builds the whole video from placeholder clips and silence, with no API calls, to check the assembly.
