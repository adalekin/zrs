import { NuxtAuthHandler } from '#auth'
import { buildAuthOptions } from '../../utils/auth-options'
import { useSettings } from '../../utils/settings'

export default NuxtAuthHandler(buildAuthOptions(useSettings()))
