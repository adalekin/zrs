<script setup lang="ts">
import { BellIcon, CircleUserIcon, LogOutIcon } from '@lucide/vue'
import { DropdownMenuContent, DropdownMenuItem, DropdownMenuPortal, DropdownMenuRoot, DropdownMenuTrigger } from 'reka-ui'

// The account on a narrow screen: one icon in the top bar that opens the name, the notifications
// and the sign-out. The bar of a phone has room for one icon, not for two.
defineProps<{ me: Me }>()

const ITEM = 'flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left outline-none data-highlighted:bg-muted [&_svg]:size-4'
</script>

<template>
  <DropdownMenuRoot>
    <DropdownMenuTrigger as-child>
      <Button variant="ghost" size="icon" :aria-label="$t('nav.account')">
        <CircleUserIcon />
      </Button>
    </DropdownMenuTrigger>
    <DropdownMenuPortal>
      <DropdownMenuContent
        align="end"
        :side-offset="6"
        class="bg-popover text-popover-foreground ring-foreground/10 z-50 grid min-w-56 rounded-xl p-1.5 text-sm shadow-md ring-1"
      >
        <div class="border-b px-2.5 pt-1.5 pb-2.5">
          <div class="font-medium">
            {{ me.name }}
          </div>
          <div class="text-muted-foreground text-xs">
            {{ me.roles.map(role => $t(`role.${role}`)).join(', ') }}
          </div>
        </div>
        <DropdownMenuItem as-child>
          <NuxtLink to="/notifications" :class="ITEM" class="mt-1.5">
            <BellIcon />{{ $t('nav.notifications') }}
          </NuxtLink>
        </DropdownMenuItem>
        <!-- A form post, as the sign-out button is: see SignOutButton. -->
        <form method="post" action="/sign-out">
          <DropdownMenuItem as-child>
            <button type="submit" :class="ITEM">
              <LogOutIcon />{{ $t('nav.signOut') }}
            </button>
          </DropdownMenuItem>
        </form>
      </DropdownMenuContent>
    </DropdownMenuPortal>
  </DropdownMenuRoot>
</template>
