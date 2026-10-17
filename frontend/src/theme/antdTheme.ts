import type { ThemeConfig } from 'antd';

const ink = '#171717';

/**
 * Easy_R 全局 Ant Design 5 主题（Supabase 风格 Phase 0）。
 *
 * 主色只用于「每个视图最多一个」的绿色实心按钮；链接、步骤条、Tab、
 * 复选框等默认会继承主色的组件全部改回近黑，避免整页泛绿。
 */
export const antdTheme: ThemeConfig = {
  token: {
    colorPrimary: '#3ecf8e',
    colorPrimaryHover: '#24b47e',
    colorPrimaryActive: '#1f9d6b',
    colorLink: ink,
    colorLinkHover: '#212121',
    colorText: ink,
    colorTextSecondary: '#707070',
    colorTextTertiary: '#707070',
    colorTextQuaternary: '#9a9a9a',
    colorBorder: '#dfdfdf',
    colorBorderSecondary: '#ededed',
    colorSplit: '#ededed',
    colorBgLayout: '#ffffff',
    colorBgContainer: '#ffffff',
    colorFillAlter: '#fafafa',
    colorSuccess: '#11845b',
    colorWarning: '#a16207',
    colorError: '#e2005a',
    colorInfo: ink,
    fontFamily: '"Inter","PingFang SC","Microsoft YaHei","Helvetica Neue",Arial,sans-serif',
    fontSize: 14,
    fontWeightStrong: 500,
    borderRadius: 6,
    borderRadiusSM: 4,
    borderRadiusLG: 12,
    borderRadiusXS: 4,
    controlHeight: 36,
    controlHeightSM: 28,
    controlHeightLG: 44,
    boxShadow: '0 1px 3px rgba(0,0,0,.06)',
    boxShadowSecondary: '0 8px 24px rgba(0,0,0,.08)',
    wireframe: false,
    motionDurationMid: '0.15s',
  },
  components: {
    Button: {
      primaryColor: ink,
      primaryShadow: 'none',
      defaultShadow: 'none',
      dangerShadow: 'none',
      defaultBorderColor: '#c7c7c7',
      defaultColor: ink,
      fontWeight: 500,
      paddingInline: 16,
    },
    Checkbox: { colorPrimary: ink, colorPrimaryHover: '#212121' },
    Radio: { colorPrimary: ink },
    Switch: { colorPrimary: ink, colorPrimaryHover: '#212121' },
    Slider: { colorPrimary: ink, colorPrimaryBorder: ink, colorPrimaryBorderHover: ink },
    Steps: { colorPrimary: ink },
    Tabs: {
      inkBarColor: ink,
      itemSelectedColor: ink,
      itemColor: '#707070',
      itemHoverColor: ink,
    },
    Menu: {
      itemBg: '#fafafa',
      itemColor: '#707070',
      itemSelectedBg: '#ededed',
      itemSelectedColor: ink,
      itemHoverBg: '#f3f3f3',
      itemBorderRadius: 6,
      itemHeight: 32,
      itemMarginInline: 8,
    },
    Layout: {
      headerBg: '#ffffff',
      siderBg: '#fafafa',
      bodyBg: '#ffffff',
      headerHeight: 48,
      headerPadding: '0 24px',
    },
    Table: {
      headerBg: '#fafafa',
      headerColor: '#707070',
      headerSplitColor: 'transparent',
      borderColor: '#ededed',
      rowHoverBg: '#fafafa',
      cellFontSize: 13,
      cellPaddingBlock: 10,
    },
    Card: { headerFontSize: 16, paddingLG: 24, borderRadiusLG: 12 },
    Input: {
      activeBorderColor: ink,
      hoverBorderColor: '#c7c7c7',
      activeShadow: '0 0 0 3px rgba(62,207,142,.25)',
    },
    Select: { optionSelectedBg: '#ededed', optionSelectedFontWeight: 500 },
    Tag: { defaultBg: '#fafafa', defaultColor: ink },
    Tooltip: { colorBgSpotlight: '#1c1c1c' },
    Progress: { defaultColor: '#3ecf8e', remainingColor: '#ededed' },
    Alert: { withDescriptionPadding: '12px 16px' },
    Modal: { borderRadiusLG: 16 },
  },
};

export default antdTheme;
