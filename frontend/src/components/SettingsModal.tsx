import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Tabs, TabsContent } from "@/components/ui/tabs";
import { useSettingsModal } from "./settings/hooks/useSettingsModal";
import { SettingsSidebar } from "./settings/SettingsSidebar";
import { AccountsTab } from "./settings/Tabs/AccountsTab";
import { AgentTab } from "./settings/Tabs/AgentTab";
import { ConversationsTab } from "./settings/Tabs/ConversationsTab";
import { GeneralTab } from "./settings/Tabs/GeneralTab";
import { GroupsTab } from "./settings/Tabs/GroupsTab";
import { PreferencesTab } from "./settings/Tabs/PreferencesTab";

interface SettingsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SettingsModal({ open, onOpenChange }: SettingsModalProps) {
  const {
    activeTab,
    setActiveTab,
    settings,
    loading,
    initialLoading,
    availableTones,
    handleSave,
  } = useSettingsModal(open, onOpenChange);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl h-[80vh] p-0 overflow-hidden flex flex-col gap-0 border-none shadow-2xl">
        <div className="flex-1 overflow-hidden flex">
          <Tabs
            defaultValue="general"
            orientation="vertical"
            className="flex w-full h-full"
            value={activeTab}
            onValueChange={setActiveTab}
          >
            <SettingsSidebar />

            <div className="flex-1 overflow-y-auto p-10">
              {initialLoading ? (
                <div className="space-y-6 animate-pulse">
                  <div className="h-8 w-1/3 bg-slate-200 rounded-lg"></div>
                  <div className="h-4 w-1/2 bg-slate-100 rounded-lg"></div>
                  <div className="h-[200px] w-full bg-slate-50 border border-slate-100 rounded-2xl"></div>
                </div>
              ) : (
                <>
                  <TabsContent value="general">
                    <GeneralTab
                      settings={settings}
                      onSave={handleSave}
                      loading={loading}
                    />
                  </TabsContent>

                  <TabsContent value="agent">
                    <AgentTab
                      settings={settings}
                      onSave={handleSave}
                      loading={loading}
                      availableTones={availableTones}
                    />
                  </TabsContent>

                  <TabsContent value="accounts">
                    <AccountsTab />
                  </TabsContent>

                  <TabsContent value="groups">
                    <GroupsTab />
                  </TabsContent>

                  <TabsContent value="conversations">
                    <ConversationsTab />
                  </TabsContent>

                  <TabsContent value="preferences">
                    <PreferencesTab
                      settings={settings}
                      onSave={handleSave}
                      loading={loading}
                    />
                  </TabsContent>
                </>
              )}
            </div>
          </Tabs>
        </div>
      </DialogContent>
    </Dialog>
  );
}
