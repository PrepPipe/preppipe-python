# SPDX-FileCopyrightText: 2023 PrepPipe's Contributors
# SPDX-License-Identifier: Apache-2.0

# stub entry point; used only for pyinstaller

import preppipe
import preppipe.pipeline_cmd
import preppipe.pipeline

if __name__ == '__main__':
  preppipe.pipeline.pipeline_main()
