# Third-Party Software Notices and Licenses

This file contains licensing and copyright notices for third-party software, libraries, tools, and artificial intelligence models used in or distributed with **SubtitleGo**.

---

## Summary of Third-Party Components

| Component | License | Project / Source |
|---|---|---|
| **PySide6 / Qt** | LGPLv3 | https://wiki.qt.io/Qt_for_Python / https://www.qt.io |
| **FFmpeg & ffprobe** | GPLv3 / LGPLv2.1+ | https://ffmpeg.org |
| **Qwen3-ASR Models & Toolkit** | Apache-2.0 | https://github.com/QwenLM/Qwen3-ASR |
| **PyTorch & TorchAudio** | BSD-3-Clause | https://pytorch.org |
| **Hugging Face Transformers** | Apache-2.0 | https://github.com/huggingface/transformers |
| **Hugging Face Accelerate** | Apache-2.0 | https://github.com/huggingface/accelerate |
| **huggingface_hub** | Apache-2.0 | https://github.com/huggingface/huggingface_hub |
| **librosa** | ISC License | https://github.com/librosa/librosa |
| **SoundFile** | BSD-3-Clause | https://github.com/bastibe/python-soundfile |
| **psutil** | BSD-3-Clause | https://github.com/giampaolo/psutil |
| **nagisa** | MIT License | https://github.com/taishi-i/nagisa |
| **PyInstaller** | GPLv2 with Exception | https://github.com/pyinstaller/pyinstaller |

---

## Detailed Notices & License Terms

### 1. PySide6 / Qt
* **License:** GNU Lesser General Public License version 3 (LGPLv3)
* **Copyright:** The Qt Company Ltd. and other contributors
* **Notice:**
  SubtitleGo uses Qt and PySide6 under the terms of the GNU Lesser General Public License version 3.
  Qt is dynamically linked, and users have the freedom to replace Qt/PySide6 shared libraries with compatible custom versions.
  Source code for Qt and PySide6 can be obtained from https://www.qt.io and https://code.qt.io/cgit/pyside/pyside-setup.git.

---

### 2. FFmpeg & ffprobe
* **License:** GNU General Public License v3.0 / GNU Lesser General Public License v2.1+
* **Copyright:** FFmpeg developers (Fabrice Bellard and the FFmpeg team)
* **Notice:**
  This software uses pre-built static binaries of FFmpeg and ffprobe for audio/video decoding, demuxing, and waveform analysis.
  FFmpeg is a trademark of Fabrice Bellard, originator of the FFmpeg project.
  Source code and build instructions for FFmpeg are available at https://ffmpeg.org.

---

### 3. Qwen3-ASR (Model Weights & Inference Library)
* **License:** Apache License 2.0
* **Copyright:** Alibaba Cloud / Qwen Team
* **Notice:**
  Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License.
  You may obtain a copy of the License at: http://www.apache.org/licenses/LICENSE-2.0

---

### 4. PyTorch and TorchAudio
* **License:** BSD-3-Clause
* **Copyright:** PyTorch Team, Facebook, Inc., and other contributors

```
Copyright (c) 2016-present, Facebook, Inc. All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

 * Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

 * Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

 * Neither the name of Facebook nor the names of its contributors may be used
   to endorse or promote products derived from this software without specific
   prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

---

### 5. Hugging Face Transformers, Accelerate & huggingface_hub
* **License:** Apache License 2.0
* **Copyright:** Hugging Face Inc. and contributors

```
                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

1. Definitions.
   "License" shall mean the terms and conditions for use, reproduction, and
   distribution as defined by Sections 1 through 9 of this document.

   "Licensor" shall mean the copyright owner or entity authorized by the copyright
   owner that is granting the License.

2. Grant of Copyright License. Subject to the terms and conditions of this License,
   each Contributor hereby grants to You a perpetual, worldwide, non-exclusive,
   no-charge, royalty-free, irrevocable copyright license to reproduce, prepare
   Derivative Works of, publicly display, publicly perform, sublicense, and
   distribute the Work and such Derivative Works in Source or Object form.

3. Grant of Patent License. Subject to the terms and conditions of this License,
   each Contributor hereby grants to You a perpetual, worldwide, non-exclusive,
   no-charge, royalty-free, irrevocable patent license to make, have made, use,
   offer to sell, sell, import, and otherwise transfer the Work.

4. Redistribution. You may reproduce and distribute copies of the Work or
   Derivative Works thereof in any medium, with or without modifications, and in
   Source or Object form, provided that You meet the following conditions:

   (a) You must give any other recipients of the Work or Derivative Works a copy of
       this License; and
   (b) You must cause any modified files to carry prominent notices stating that You
       changed the files; and
   (c) You must retain, in the Source form of any Derivative Works that You distribute,
       all copyright, patent, trademark, and attribution notices from the Source form
       of the Work; and
   (d) If the Work includes a "NOTICE" text file as part of its distribution, then any
       Derivative Works that You distribute must include a readable copy of the
       attribution notices contained within such NOTICE file.
```

---

### 6. librosa
* **License:** ISC License
* **Copyright:** Brian McFee, Colin Raffel, Dawen Liang, Daniel P.W. Ellis, Matt McVicar, Eric Battenberg, Oriol Nieto

```
Permission to use, copy, modify, and/or distribute this software for any purpose with
or without fee is hereby granted, provided that the above copyright notice and this
permission notice appear in all copies.

THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES WITH
REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT, INDIRECT,
OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA
OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
```

---

### 7. SoundFile (python-soundfile)
* **License:** BSD-3-Clause
* **Copyright:** 2013-2023 Bastian Bechtold

```
Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its contributors
   may be used to endorse or promote products derived from this software without
   specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

---

### 8. psutil
* **License:** BSD-3-Clause
* **Copyright:** 2009-2024 Jay Loden, Dave Daeschler, Giampaolo Rodola

```
Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

 * Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.
 * Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.
 * Neither the name of psutil authors nor the names of its contributors may
   be used to endorse or promote products derived from this software without
   specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

---

### 9. nagisa
* **License:** MIT License
* **Copyright:** 2018 Taishi Ikeda

```
Permission is hereby granted, free of charge, to any person obtaining a copy of this
software and associated documentation files (the "Software"), to deal in the Software
without restriction, including without limitation the rights to use, copy, modify,
merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to the following
conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN
AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

---

### 10. PyInstaller
* **License:** GNU General Public License v2.0 with PyInstaller Bootloader Exception
* **Copyright:** 2010-2024 PyInstaller Development Team
* **Notice:**
  Programs packaged with PyInstaller are not required to be open source under the GPL, thanks to the special Bootloader Exception granted by the PyInstaller copyright holders.
