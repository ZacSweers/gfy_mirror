gfy_mirror
==========

Reddit bot to mirror gifs and gfys across a few different services while also converting gifs and vines to a "gfy" .mp4 format.

*If you would like to use this bot on your subreddit, please drop me an [email](mailto:pandanomic@gmail.com) and I'd be happy to look into adding it. This source is for reference, not to flood reddit with multiple clones of the same bot :P*

### Basic flow
- Runs on Heroku, using the free scheduler.
- If it finds a new gif/gfy/vine, it re-uploads to a few different mirrors
  - Including conversion from gif/vine to gfy/mp4 if necessary
  
### Supported services
- Gfycat
- Imgrush
- Offsided

### TODO
- Currently, it won't re-mirror Offsided videos due to no easily available API for retrieving the .mp4 url. I can extract it manually though via the html, the same way I handle Vines.
- Re-host gifs on imgur
- I plan to eventually use a full database for this, where each MirrorObject is represented by a row. This way, if I ever come across a URL that's just a mirror of a pre-existing one, I can just retrieve it directly from the DB and save processing time on my end and the services' APIs.

### Credits
- [PyCrush](https://github.com/MediaCrush/PyCrush) API wrapper for Imgrush (which is a fork of the now defunct Mediacrush)

### License

     The MIT License (MIT)

	 Copyright (c) 2014 Henri (Zac) Sweers

	 Permission is hereby granted, free of charge, to any person obtaining a copy of
	 this software and associated documentation files (the "Software"), to deal in
	 the Software without restriction, including without limitation the rights to
	 use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
	 the Software, and to permit persons to whom the Software is furnished to do so,
	 subject to the following conditions:

	 The above copyright notice and this permission notice shall be included in all
	 copies or substantial portions of the Software.

	 THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
	 IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
	 FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
	 COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
	 IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
	 CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
